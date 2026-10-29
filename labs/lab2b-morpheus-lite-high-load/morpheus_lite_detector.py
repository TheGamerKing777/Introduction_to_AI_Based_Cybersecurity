from __future__ import annotations

import random
import time
from collections import defaultdict

from sklearn.ensemble import IsolationForest

from morpheus_lite.config import load_settings
from morpheus_lite.fingerprinting import FingerprintStore
from morpheus_lite.kafka_io import create_consumer, create_producer, publish
from morpheus_lite.observability import start_metrics, timed
from morpheus_lite.high_load import LoadMetricsStore, RollingRate, epoch_ms, processing_delay_seconds

RISKY_COUNTRIES = {"RU", "CN", "IR", "KP"}
SUSPICIOUS_EVENT_TYPES = {"privilege_escalation", "suspicious_process"}


def extract_features(event: dict) -> list[float]:
    return [
        float(event.get("failed_logins", 0)),
        float(event.get("bytes_out", 0)),
        float(event.get("process_count", 0)),
        1.0 if event.get("country") in RISKY_COUNTRIES else 0.0,
        1.0 if event.get("event_type") in SUSPICIOUS_EVENT_TYPES else 0.0,
    ]


def train_baseline_model() -> IsolationForest:
    normal_samples = [
        [random.randint(0, 3), random.randint(1_000, 500_000), random.randint(20, 120), 0, 0]
        for _ in range(500)
    ]
    model = IsolationForest(n_estimators=100, contamination=0.12, random_state=42)
    model.fit(normal_samples)
    return model


def explain_event(event: dict) -> list[str]:
    reasons: list[str] = []
    if event.get("failed_logins", 0) >= 8:
        reasons.append("high number of failed login attempts")
    if event.get("bytes_out", 0) >= 5_000_000:
        reasons.append("large outbound data transfer")
    if event.get("process_count", 0) >= 150:
        reasons.append("abnormally high process count")
    if event.get("country") in RISKY_COUNTRIES:
        reasons.append("login/source country is outside normal profile")
    if event.get("event_type") in SUSPICIOUS_EVENT_TYPES:
        reasons.append(f"suspicious event type: {event.get('event_type')}")
    return reasons


def score_event(event: dict, model: IsolationForest, fingerprint: dict) -> tuple[int, list[str], float, int, list[float]]:
    features = extract_features(event)
    prediction = int(model.predict([features])[0])
    anomaly_score = float(model.decision_function([features])[0])
    reasons = explain_event(event)
    risk_score = 70 if prediction == -1 else 20
    if prediction == -1:
        reasons.append("Isolation Forest marked this event as anomalous")
    if fingerprint.get("user_specific") and fingerprint.get("max_z_score", 0) >= 3:
        reasons.append(f"user-specific fingerprint deviation z={fingerprint['max_z_score']}")
        risk_score = max(risk_score, 80)
    evidence_count = len([r for r in reasons if not r.startswith("Isolation Forest")])
    risk_score = max(risk_score, {0: 20, 1: 50, 2: 70, 3: 85}.get(evidence_count, 100))
    return min(risk_score, 100), reasons, anomaly_score, prediction, features


def main() -> None:
    settings = load_settings()
    storage = settings.raw.get("storage", {})
    fingerprint_store = FingerprintStore(storage.get("fingerprint_state", "data/fingerprint_profiles.json"))
    model = train_baseline_model()
    if settings.raw.get("observability", {}).get("enabled", True):
        start_metrics(int(settings.raw.get("observability", {}).get("prometheus_port", 9108)) + 1)
    consumer = create_consumer(settings, "raw_events", "morpheus-lite-detector-ml")
    producer = create_producer(settings)
    metrics = LoadMetricsStore(settings.raw.get("high_load", {}).get("metrics_jsonl", "data/high_load_metrics.jsonl"))
    delay = processing_delay_seconds(settings.raw, "detector")
    processed_by_run: dict[str, int] = defaultdict(int)
    alerts_by_run: dict[str, int] = defaultdict(int)
    rates: dict[str, RollingRate] = {}
    window = float(settings.raw.get("high_load", {}).get("throughput_window_seconds", 5.0))
    print("Isolation Forest and user fingerprinting initialized")

    for message in consumer:
        event = message.value
        try:
            with timed("detector"):
                stage_started = time.perf_counter()
                stage_started_epoch_ms = epoch_ms()
                generated_ms = event.get("generated_epoch_ms")
                queue_wait_ms = max(0.0, stage_started_epoch_ms - float(generated_ms)) if generated_ms is not None else 0.0
                if delay:
                    time.sleep(delay)
                fingerprint = fingerprint_store.score(event)
                score, reasons, anomaly_score, prediction, features = score_event(event, model, fingerprint)
                trusted_normal = score < 60 and event.get("label") != "suspicious"
                fingerprint_store.update(event, trusted_normal=trusted_normal)
                if score >= settings.policies.get("thresholds", {}).get("alert", 60):
                    alert = {
                        "alert_id": f"alert-{message.partition}-{message.offset}",
                        "correlation_id": event.get("correlation_id", f"raw-{message.partition}-{message.offset}"),
                        "source_event": event,
                        "risk_score": score,
                        "detector": "isolation-forest-plus-user-fingerprint",
                        "ml_model": "IsolationForest",
                        "isolation_forest_prediction": prediction,
                        "anomaly_score": anomaly_score,
                        "fingerprint": fingerprint,
                        "features": {
                            "failed_logins": features[0],
                            "bytes_out": features[1],
                            "process_count": features[2],
                            "risky_country": features[3],
                            "suspicious_event_type": features[4],
                        },
                        "reasons": reasons,
                        "status": "new",
                        "detected_epoch_ms": epoch_ms(),
                    }
                    publish(producer, settings.topic("alerts"), alert)
                    run_id = str(event.get("load_run_id") or "legacy")
                    alerts_by_run[run_id] += 1
                    print("ALERT:", alert["alert_id"], score, reasons)
                run_id = str(event.get("load_run_id") or "legacy")
                profile = event.get("load_profile", "unknown")
                processed_by_run[run_id] += 1
                rate = rates.setdefault(run_id, RollingRate(window)).mark()
                end_to_end_ms = max(0.0, epoch_ms() - float(generated_ms)) if generated_ms is not None else 0.0
                stage_ms = (time.perf_counter() - stage_started) * 1000
                metrics.record("detector", "events_processed", processed_by_run[run_id], profile=profile, run_id=run_id)
                metrics.record("detector", "alerts_emitted", alerts_by_run[run_id], profile=profile, run_id=run_id)
                metrics.record("detector", "throughput_eps", rate, profile=profile, run_id=run_id)
                metrics.record("detector", "queue_wait_ms", queue_wait_ms, profile=profile, run_id=run_id)
                metrics.record("detector", "stage_latency_ms", stage_ms, profile=profile, run_id=run_id)
                metrics.record("detector", "end_to_end_latency_ms", end_to_end_ms, profile=profile, run_id=run_id)
        except Exception as exc:
            publish(producer, settings.topic("dead_letter"), {"component": "detector", "event": event, "error": str(exc)})
            print(f"Detector error: {exc}")


if __name__ == "__main__":
    main()
