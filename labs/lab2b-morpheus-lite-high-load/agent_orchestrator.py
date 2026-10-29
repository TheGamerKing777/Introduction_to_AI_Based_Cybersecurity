from __future__ import annotations

import json
import time
from collections import defaultdict

from morpheus_lite.config import load_settings
from morpheus_lite.inference import InferenceRequest, ResilientInference
from morpheus_lite.inference.providers import DeterministicProvider
from morpheus_lite.kafka_io import (
    create_consumer,
    create_producer,
    ephemeral_group_id,
    publish,
    wait_for_assignment,
)
from morpheus_lite.meta_ai import MetaAIAgent
from morpheus_lite.observability import start_metrics, timed
from morpheus_lite.high_load import LoadMetricsStore, RollingRate, epoch_ms, processing_delay_seconds
from morpheus_lite.storage import AuditStore


def threat_hunter_agent(alert: dict) -> dict:
    event = alert["source_event"]
    findings: list[str] = []
    if event.get("event_type") in {"privilege_escalation", "suspicious_process"}:
        findings.append("Possible post-compromise activity detected.")
    if event.get("failed_logins", 0) >= 8:
        findings.append("Authentication anomaly suggests brute force or credential stuffing.")
    if event.get("bytes_out", 0) >= 5_000_000:
        findings.append("Possible data exfiltration pattern.")
    if alert.get("fingerprint", {}).get("max_z_score", 0) >= 3:
        findings.append("User behavior deviates significantly from the historical fingerprint.")
    return {
        "agent": "Threat Hunter Agent",
        "findings": findings,
        "mitre_mapping": [
            "TA0006 Credential Access",
            "TA0010 Exfiltration",
            "TA0004 Privilege Escalation",
        ],
    }


def rai_policy_agent(alert: dict, investigation: dict, policies: dict) -> dict:
    risk = float(alert["risk_score"])
    thresholds = policies.get("thresholds", {})
    actions = policies.get("actions", {})
    high = float(thresholds.get("high_risk", 85))
    medium = float(thresholds.get("alert", 60))
    if risk >= high:
        action = actions.get("high_risk", "recommend_isolation_with_human_approval")
        allowed = True
        note = "High risk. Isolation may be recommended, but human approval is required."
    elif risk >= medium:
        action = actions.get("medium_risk", "increase_monitoring")
        allowed = True
        note = "Medium risk. Automated destructive actions are blocked."
    else:
        action = actions.get("low_risk", "no_action")
        allowed = False
        note = "Risk below response threshold."
    return {
        "agent": "RAI Policy Agent",
        "allowed": allowed,
        "recommended_action": action,
        "policy_note": note,
        "human_approval_required": action == "recommend_isolation_with_human_approval",
        "policy_evidence_count": len(alert.get("reasons", [])),
    }


def build_prompt(alert: dict, investigation: dict, rai: dict) -> str:
    return f"""
You are an Explainable AI cybersecurity SOC agent.
Explain the following alert for a SOC analyst.

Alert:
{json.dumps(alert, indent=2)}

Threat Hunter Findings:
{json.dumps(investigation, indent=2)}

Responsible-AI Policy:
{json.dumps(rai, indent=2)}

Include: trigger reason, strongest evidence, MITRE ATT&CK interpretation,
uncertainty, why human approval may be required, and the recommended next step.
"""


def main() -> None:
    settings = load_settings()
    inference_config = settings.raw.get("inference", {})
    inference = ResilientInference(inference_config)
    high_load_cfg = settings.raw.get("high_load", {})
    lab_xai_provider = str(high_load_cfg.get("lab_xai_provider", "deterministic")).lower()
    lab_inference = DeterministicProvider("high-load-rule-based-explainer") if lab_xai_provider == "deterministic" else inference
    meta_agent = MetaAIAgent()
    storage_cfg = settings.raw.get("storage", {})
    audit_store = AuditStore(
        storage_cfg.get("audit_jsonl", "data/audit.jsonl"),
        storage_cfg.get("parquet_directory", "exports"),
    )
    if settings.raw.get("observability", {}).get("enabled", True):
        start_metrics(int(settings.raw.get("observability", {}).get("prometheus_port", 9108)))

    # Use one consumer group per process instance. A fixed group id can leave a
    # still-running or stale orchestrator competing for the same partition,
    # making the new terminal appear healthy while it receives zero records.
    consumer_group = ephemeral_group_id("agent-orchestrator")
    consumer = create_consumer(
        settings,
        "alerts",
        consumer_group,
        auto_offset_reset="latest",
        client_id=consumer_group,
    )
    producer = create_producer(settings)
    metrics = LoadMetricsStore(settings.raw.get("high_load", {}).get("metrics_jsonl", "data/high_load_metrics.jsonl"))
    delay = processing_delay_seconds(settings.raw, "orchestrator")
    received_by_run: dict[str, int] = defaultdict(int)
    processed_by_run: dict[str, int] = defaultdict(int)
    failed_by_run: dict[str, int] = defaultdict(int)
    rates: dict[str, RollingRate] = {}
    window = float(settings.raw.get("high_load", {}).get("throughput_window_seconds", 5.0))
    topic = settings.topic("alerts")
    try:
        assignment = wait_for_assignment(consumer, timeout_seconds=10.0)
    except Exception as exc:
        print(f"Orchestrator startup failed: {exc}")
        consumer.close()
        producer.close()
        raise
    partitions = ", ".join(sorted(f"{tp.topic}:{tp.partition}" for tp in assignment))
    print(
        f"Agent orchestrator ready on {topic} "
        f"[group={consumer_group}; partitions={partitions}]"
    )
    print("Start the telemetry generator only after this READY message appears.")

    for message in consumer:
        alert = message.value
        try:
            with timed("agent_orchestration"):
                stage_started = time.perf_counter()
                stage_started_epoch_ms = epoch_ms()
                event = alert.get("source_event", {})
                run_id = str(event.get("load_run_id") or "legacy")
                profile = event.get("load_profile", "unknown")
                received_by_run[run_id] += 1
                metrics.record("orchestrator", "events_received", received_by_run[run_id], profile=profile, run_id=run_id)
                detected_ms = alert.get("detected_epoch_ms")
                queue_wait_ms = max(0.0, stage_started_epoch_ms - float(detected_ms)) if detected_ms is not None else 0.0
                if delay:
                    time.sleep(delay)
                investigation = threat_hunter_agent(alert)
                rai = rai_policy_agent(alert, investigation, settings.policies)
                active_inference = lab_inference if run_id != "legacy" else inference
                response = active_inference.predict(
                    InferenceRequest(
                        prompt=build_prompt(alert, investigation, rai),
                        model=inference_config.get("model"),
                        inputs={
                            "risk_score": alert.get("risk_score"),
                            "evidence": alert.get("reasons", []),
                            "recommended_action": rai.get("recommended_action"),
                        },
                    )
                )
                xai = {
                    "agent": f"{response.provider} XAI Agent",
                    "alert_id": alert["alert_id"],
                    "plain_language_explanation": response.output,
                    "evidence": alert.get("reasons", []),
                    "confidence": alert.get("risk_score", 0) / 100,
                    "provider": response.provider,
                    "model": response.model,
                    "latency_ms": round(response.latency_ms, 2),
                    "fallback_used": response.fallback_used,
                    "provider_metadata": response.metadata,
                }
                final_case = {"alert": alert, "investigation": investigation, "rai": rai, "xai": xai}
                meta_ai = meta_agent.review(final_case)
                final_case["meta_ai"] = meta_ai
                final_case["status"] = "awaiting_human_decision" if rai["human_approval_required"] or not meta_ai["approved"] else "reviewed"

                # Enqueue all records and flush once. Flushing after every topic
                # serialized the stage around Kafka round trips and could make the
                # orchestrator appear stalled during Lab 2b.
                publish(producer, settings.topic("investigations"), final_case, flush=False)
                publish(producer, settings.topic("explanations"), xai, flush=False)
                publish(producer, settings.topic("rai_audit"), rai, flush=False)
                publish(producer, settings.topic("meta_ai"), meta_ai, flush=False)
                producer.flush()
                audit_store.append(final_case)
                processed_by_run[run_id] += 1
                rate = rates.setdefault(run_id, RollingRate(window)).mark()
                stage_ms = (time.perf_counter() - stage_started) * 1000
                generated_ms = event.get("generated_epoch_ms")
                e2e_ms = max(0.0, epoch_ms() - float(generated_ms)) if generated_ms is not None else 0.0
                metrics.record("orchestrator", "events_processed", processed_by_run[run_id], profile=profile, run_id=run_id)
                metrics.record("orchestrator", "throughput_eps", rate, profile=profile, run_id=run_id)
                metrics.record("orchestrator", "queue_wait_ms", queue_wait_ms, profile=profile, run_id=run_id)
                metrics.record("orchestrator", "stage_latency_ms", stage_ms, profile=profile, run_id=run_id)
                metrics.record("orchestrator", "end_to_end_latency_ms", e2e_ms, profile=profile, run_id=run_id)
                metrics.record("orchestrator", "xai_latency_ms", float(response.latency_ms), profile=profile, run_id=run_id, provider=response.provider)
                print(f"Processed {alert['alert_id']} -> {final_case['status']}")
        except Exception as exc:
            event = alert.get("source_event", {}) if isinstance(alert, dict) else {}
            run_id = str(event.get("load_run_id") or "legacy")
            profile = event.get("load_profile", "unknown")
            failed_by_run[run_id] += 1
            metrics.record("orchestrator", "events_failed", failed_by_run[run_id], profile=profile, run_id=run_id, error=str(exc))
            publish(
                producer,
                settings.topic("dead_letter"),
                {"component": "agent_orchestrator", "alert": alert, "error": str(exc)},
            )
            print(f"Failed to process alert: {exc}")


if __name__ == "__main__":
    main()
