from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from morpheus_lite.config import load_settings
from morpheus_lite.kafka_io import create_consumer, create_producer, publish
from morpheus_lite.storage import AuditStore

settings = load_settings()
st.set_page_config(page_title="Morpheus Lite Agentic SOC", layout="wide")
st.title("Morpheus Lite Agentic SOC Dashboard")
st.caption("Kafka -> Detection -> Agent Orchestration -> RAI -> Meta-AI -> Human Decision")

if "cases" not in st.session_state:
    st.session_state.cases = []
if "decisions" not in st.session_state:
    st.session_state.decisions = {}
if "selected_alert_id" not in st.session_state:
    st.session_state.selected_alert_id = None

DECISION_OPTIONS = [
    "approve",
    "reject",
    "escalate",
    "request_more_evidence",
    "defer",
]


def fetch_cases() -> int:
    consumer = create_consumer(
        settings,
        "investigations",
        None,
        auto_offset_reset="earliest",
        consumer_timeout_ms=2500,
    )
    existing = {c["alert"]["alert_id"] for c in st.session_state.cases}
    count = 0
    try:
        for message in consumer:
            case = message.value
            alert_id = case.get("alert", {}).get("alert_id")
            if alert_id and alert_id not in existing:
                st.session_state.cases.append(case)
                existing.add(alert_id)
                count += 1
    finally:
        consumer.close()
    return count


def record_decision(case: dict[str, Any], decision: str, justification: str) -> None:
    alert = case["alert"]
    alert_id = alert["alert_id"]
    record = {
        "alert_id": alert_id,
        "correlation_id": alert.get("correlation_id"),
        "decision": decision,
        "justification": justification.strip(),
        "risk_score": alert.get("risk_score"),
        "rai_recommendation": case.get("rai", {}).get("recommended_action"),
        "meta_ai_disposition": case.get("meta_ai", {}).get("disposition"),
    }

    producer = create_producer(settings)
    try:
        publish(producer, settings.topic("human_decisions"), record)
    finally:
        producer.close()

    AuditStore(
        settings.raw.get("storage", {}).get("audit_jsonl", "data/audit.jsonl"),
        settings.raw.get("storage", {}).get("parquet_directory", "exports"),
    ).append({"human_decision": record})

    st.session_state.decisions[alert_id] = decision


def render_decision_form(case: dict[str, Any], *, key_prefix: str) -> None:
    alert_id = case["alert"]["alert_id"]
    current = st.session_state.decisions.get(alert_id)

    if current:
        st.success(f"Decision already recorded: {current}")
        return

    with st.form(key=f"decision-form-{key_prefix}-{alert_id}", clear_on_submit=False):
        decision = st.selectbox(
            "Human decision",
            DECISION_OPTIONS,
            key=f"decision-{key_prefix}-{alert_id}",
        )
        justification = st.text_area(
            "Decision justification",
            placeholder="Explain the evidence, uncertainty, or policy rationale for this decision.",
            key=f"justification-{key_prefix}-{alert_id}",
        )
        submitted = st.form_submit_button("Record decision", type="primary")

    if submitted:
        try:
            record_decision(case, decision, justification)
        except Exception as exc:
            st.error(f"Could not record the decision: {exc}")
        else:
            st.success(f"Decision '{decision}' recorded for {alert_id}")
            st.rerun()


def sync_queue_to_active(widget_key: str) -> None:
    """Make the queue selection the single active alert."""
    selected = st.session_state.get(widget_key)
    if selected:
        st.session_state.selected_alert_id = selected


if st.button("Fetch new cases from Kafka"):
    try:
        st.success(f"Fetched {fetch_cases()} new cases")
    except Exception as exc:
        st.error(f"Could not fetch cases from Kafka: {exc}")

cases = st.session_state.cases
pending_reviews = [
    c
    for c in cases
    if st.session_state.decisions.get(c["alert"]["alert_id"]) is None
    and (
        bool(c.get("rai", {}).get("human_approval_required"))
        or c.get("meta_ai", {}).get("disposition") == "escalate"
    )
]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Cases", len(cases))
col2.metric("High Risk", sum(c["alert"].get("risk_score", 0) >= 85 for c in cases))
col3.metric("Pending Human Review", len(pending_reviews))
col4.metric(
    "Meta-AI Escalations",
    sum(c.get("meta_ai", {}).get("disposition") == "escalate" for c in cases),
)

if cases:
    cases_by_id = {case["alert"]["alert_id"]: case for case in cases}
    valid_ids = list(cases_by_id)

    if st.session_state.selected_alert_id not in cases_by_id:
        st.session_state.selected_alert_id = (
            pending_reviews[-1]["alert"]["alert_id"] if pending_reviews else valid_ids[-1]
        )

    # ------------------------------------------------------------------
    # ALL CASES: clicking a row changes the shared selected_alert_id.
    # ------------------------------------------------------------------
    rows = []
    for case in cases:
        alert = case["alert"]
        event = alert.get("source_event", {})
        alert_id = alert["alert_id"]
        rows.append(
            {
                "alert_id": alert_id,
                "risk_score": alert.get("risk_score"),
                "user": event.get("user"),
                "host": event.get("host"),
                "event_type": event.get("event_type"),
                "fingerprint_z": alert.get("fingerprint", {}).get("max_z_score", 0),
                "provider": case.get("xai", {}).get("provider"),
                "rai_approval_required": case.get("rai", {}).get("human_approval_required", False),
                "meta_ai": case.get("meta_ai", {}).get("disposition"),
                "human_decision": st.session_state.decisions.get(alert_id, "pending"),
            }
        )

    st.subheader("All Cases")
    st.caption("Select a case using the checkbox in the first column.")
    cases_df = pd.DataFrame(rows)

    # Use an explicit editable selection column. This is more reliable across
    # Streamlit versions than st.dataframe row-selection events.
    cases_df.insert(
        0,
        "select",
        cases_df["alert_id"].eq(st.session_state.selected_alert_id),
    )

    editor_key = f"all_cases_editor_{st.session_state.selected_alert_id}"
    edited_df = st.data_editor(
        cases_df,
        use_container_width=True,
        hide_index=True,
        key=editor_key,
        num_rows="fixed",
        disabled=[column for column in cases_df.columns if column != "select"],
        column_config={
            "select": st.column_config.CheckboxColumn(
                "Select",
                help="Select this alert as the active case.",
                default=False,
            )
        },
    )

    checked_ids = edited_df.loc[edited_df["select"], "alert_id"].astype(str).tolist()
    newly_checked_ids = [
        alert_id
        for alert_id in checked_ids
        if alert_id != st.session_state.selected_alert_id
    ]

    if newly_checked_ids:
        # A newly checked row becomes the single active alert. The dynamic
        # editor key resets the table on rerun so only that row remains checked.
        st.session_state.selected_alert_id = newly_checked_ids[-1]
        st.rerun()
    elif not checked_ids:
        # Keep an active selection even if the user clears the current checkbox.
        cases_df.loc[
            cases_df["alert_id"].eq(st.session_state.selected_alert_id),
            "select",
        ] = True

    st.info(f"Active alert: {st.session_state.selected_alert_id}")

    # ------------------------------------------------------------------
    # HUMAN DECISION WORKBENCH: always follows selected_alert_id.
    # ------------------------------------------------------------------
    st.subheader("Human Decision Queue")

    # Include every case so the queue/workbench can always synchronize with
    # the selection made in All Cases. Pending status is shown in the label.
    queue_ids = [case["alert"]["alert_id"] for case in reversed(cases)]

    def queue_label(alert_id: str) -> str:
        queue_case = cases_by_id[alert_id]
        alert = queue_case["alert"]
        event = alert.get("source_event", {})
        decision = st.session_state.decisions.get(alert_id)
        approval_required = bool(queue_case.get("rai", {}).get("human_approval_required"))
        meta_escalated = queue_case.get("meta_ai", {}).get("disposition") == "escalate"

        if decision:
            status = f"DECIDED: {decision}"
        elif approval_required or meta_escalated:
            status = "REVIEW REQUIRED"
        else:
            status = "OPTIONAL REVIEW"

        return (
            f"{status}: {alert_id} | Risk {alert.get('risk_score')} | "
            f"{event.get('event_type')} | {event.get('host')}"
        )

    # The widget key includes the active alert. When All Cases changes the
    # active alert, Streamlit creates a fresh queue widget whose initial
    # index points to that same alert. This avoids stale selectbox state.
    active_alert_id = st.session_state.selected_alert_id
    queue_index = queue_ids.index(active_alert_id) if active_alert_id in queue_ids else 0
    queue_widget_key = f"decision_queue_alert_id__{active_alert_id}"

    queue_alert_id = st.selectbox(
        "Selected case for human review",
        queue_ids,
        index=queue_index,
        key=queue_widget_key,
        on_change=sync_queue_to_active,
        args=(queue_widget_key,),
        format_func=queue_label,
    )

    # On the render where the user changes the queue, the callback already
    # updates selected_alert_id before the script reruns. This guard also
    # keeps the state correct on Streamlit versions with different callback
    # timing.
    if queue_alert_id != st.session_state.selected_alert_id:
        st.session_state.selected_alert_id = queue_alert_id
        st.rerun()
    queue_case = cases_by_id[queue_alert_id]
    queue_decision = st.session_state.decisions.get(queue_alert_id)
    queue_requires_review = (
        bool(queue_case.get("rai", {}).get("human_approval_required"))
        or queue_case.get("meta_ai", {}).get("disposition") == "escalate"
    )

    if queue_decision:
        st.success(f"Human decision already recorded: {queue_decision}")
    elif queue_requires_review:
        st.warning("This case requires human review.")
    else:
        st.info("This case does not require mandatory approval, but an analyst may still review it.")

    st.write("### XAI Explanation")
    st.write(queue_case.get("xai", {}).get("plain_language_explanation", "No explanation available."))
    st.write("### Evidence")
    st.write(queue_case.get("xai", {}).get("evidence", []))

    left, right = st.columns(2)
    with left:
        st.write("### RAI Decision")
        st.json(queue_case.get("rai", {}))
    with right:
        st.write("### Meta-AI Review")
        st.json(queue_case.get("meta_ai", {}))

    st.divider()
    st.write("### Analyst Decision")
    render_decision_form(queue_case, key_prefix="queue")

    # ------------------------------------------------------------------
    # CASE DETAILS: always renders the shared selected_alert_id.
    # ------------------------------------------------------------------
    st.subheader("Case Details")
    selected_case = cases_by_id[st.session_state.selected_alert_id]
    alert = selected_case["alert"]
    correlation_id = alert.get("correlation_id", "not available")
    st.caption(
        f"Alert ID: {st.session_state.selected_alert_id} | Correlation ID: {correlation_id}"
    )

    st.write("### XAI Explanation")
    st.write(selected_case.get("xai", {}).get("plain_language_explanation", "No explanation available."))
    st.write("### Evidence")
    st.write(selected_case.get("xai", {}).get("evidence", []))

    left, right = st.columns(2)
    with left:
        st.write("### RAI Decision")
        st.json(selected_case.get("rai", {}))
    with right:
        st.write("### Meta-AI Review")
        st.json(selected_case.get("meta_ai", {}))

    st.divider()
    st.write("### Human Decision")
    render_decision_form(selected_case, key_prefix="details")
else:
    st.info("No cases yet. Start Redpanda, telemetry, detector, and orchestrator, then fetch cases.")

# ------------------------------------------------------------------
# LAB 2B: HIGH-LOAD OBSERVABILITY
# ------------------------------------------------------------------
# ------------------------------------------------------------------
# LAB 2B: HIGH-LOAD OBSERVABILITY
# ------------------------------------------------------------------
st.divider()
st.subheader("Lab 2b – High-Load Observability")
st.caption("Run telemetry_generator.py with --profile normal, burst, sustained, or attack_surge, then refresh these measurements.")

from morpheus_lite.high_load import LoadMetricsStore, system_status

high_load_cfg = settings.raw.get("high_load", {})
metrics_path = high_load_cfg.get("metrics_jsonl", "data/high_load_metrics.jsonl")
metrics_store = LoadMetricsStore(metrics_path)
if st.button("Refresh high-load metrics"):
    st.rerun()

metric_records = metrics_store.read(limit=100000)
if metric_records:
    metrics_df = pd.DataFrame(metric_records)
    labels_df = pd.json_normalize(metrics_df.pop("labels")).add_prefix("label.")
    metrics_df = pd.concat([metrics_df, labels_df], axis=1)
    metrics_df["timestamp"] = pd.to_datetime(metrics_df["timestamp"], errors="coerce", utc=True)
    metrics_df["value"] = pd.to_numeric(metrics_df["value"], errors="coerce")

    run_col = "label.run_id"
    valid_runs = metrics_df.dropna(subset=[run_col]) if run_col in metrics_df.columns else pd.DataFrame()
    if not valid_runs.empty:
        run_starts = valid_runs[valid_runs.metric == "run_started"].sort_values("timestamp")
        latest_run = str(run_starts.iloc[-1][run_col]) if not run_starts.empty else str(valid_runs.sort_values("timestamp").iloc[-1][run_col])
        run_df = valid_runs[valid_runs[run_col].astype(str) == latest_run].copy()
        profile_values = run_df.get("label.profile", pd.Series(dtype=str)).dropna()
        profile_name = str(profile_values.iloc[-1]) if not profile_values.empty else "unknown"
        st.caption(f"Latest experiment: {profile_name} | run_id: {latest_run[:8]}")
    else:
        run_df = metrics_df.copy()
        latest_run = "legacy"
        profile_name = "legacy"
        st.warning("Displaying legacy metrics. Run a new telemetry profile to obtain per-run measurements.")

    run_df = run_df.dropna(subset=["timestamp"]).sort_values("timestamp")
    run_start = run_df["timestamp"].min()
    run_df["elapsed_s"] = (run_df["timestamp"] - run_start).dt.total_seconds().round(2)
    latest = run_df.groupby(["component", "metric"], as_index=False).tail(1)

    def latest_value(component: str, metric: str, default: float = 0.0) -> float:
        values = latest.loc[(latest.component == component) & (latest.metric == metric), "value"].dropna()
        return float(values.iloc[-1]) if not values.empty else default

    def recent_mean(component: str, metric: str, n: int = 200) -> float | None:
        values = run_df.loc[(run_df.component == component) & (run_df.metric == metric), "value"].dropna().tail(n)
        return float(values.mean()) if not values.empty else None

    gen_rate = latest_value("generator", "throughput_eps")
    det_rate = latest_value("detector", "throughput_eps")
    orch_rate = latest_value("orchestrator", "throughput_eps")
    generated = int(latest_value("generator", "events_sent"))
    detected = int(latest_value("detector", "events_processed"))
    alerts = int(latest_value("detector", "alerts_emitted"))
    orchestrator_received = int(latest_value("orchestrator", "events_received"))
    orchestrated = int(latest_value("orchestrator", "events_processed"))
    orchestrator_failed = int(latest_value("orchestrator", "events_failed"))

    ingress_backlog = max(0, generated - detected)
    alert_backlog = max(0, alerts - orchestrated)
    capacities = high_load_cfg.get("queue_capacity", {})
    ingress_capacity = int(capacities.get("ingress", 500))
    alert_capacity = int(capacities.get("alerts", 500))

    det_stage = recent_mean("detector", "stage_latency_ms") or 0.0
    orch_stage = recent_mean("orchestrator", "stage_latency_ms") or 0.0
    det_util = min(100.0, det_rate * det_stage / 10.0)
    orch_util = min(100.0, orch_rate * orch_stage / 10.0)

    thresholds = high_load_cfg.get("status_thresholds", {})
    health, health_explanation = system_status(
        det_util,
        orch_util,
        ingress_backlog,
        alert_backlog,
        warning_utilization=float(thresholds.get("warning_utilization", 70)),
        critical_utilization=float(thresholds.get("critical_utilization", 90)),
        warning_backlog_ratio=float(thresholds.get("warning_backlog_ratio", 0.50)),
        critical_backlog_ratio=float(thresholds.get("critical_backlog_ratio", 0.85)),
        ingress_capacity=ingress_capacity,
        alert_capacity=alert_capacity,
    )
    if health == "OVERLOADED":
        st.error(f"System status: {health} — {health_explanation}")
    elif health == "HIGH LOAD":
        st.warning(f"System status: {health} — {health_explanation}")
    else:
        st.success(f"System status: {health} — {health_explanation}")

    detector_e2e = recent_mean("detector", "end_to_end_latency_ms")
    orchestrator_e2e = recent_mean("orchestrator", "end_to_end_latency_ms")
    detector_queue = recent_mean("detector", "queue_wait_ms")
    orchestrator_queue = recent_mean("orchestrator", "queue_wait_ms")

    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Generated events/s", f"{gen_rate:.1f}")
    h2.metric("Detector events/s", f"{det_rate:.1f}")
    h3.metric("Orchestrator alerts/s", f"{orch_rate:.1f}" if orchestrated else "waiting")
    h4.metric("Full-pipeline E2E latency", f"{orchestrator_e2e:.1f} ms" if orchestrator_e2e is not None else "waiting")

    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Ingress backlog", f"{ingress_backlog} / {ingress_capacity}")
    q2.metric("Alert backlog", f"{alert_backlog} / {alert_capacity}")
    q3.metric("Detector utilization", f"{det_util:.1f}%")
    q4.metric("Orchestrator utilization", f"{orch_util:.1f}%" if orchestrated else "waiting")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Generated", generated)
    c2.metric("Detected", detected)
    c3.metric("Alerts", alerts)
    c4.metric("Orchestrator received", orchestrator_received)
    c5.metric("Orchestrated", orchestrated)

    st.markdown("**Pipeline health**")
    p1, p2, p3, p4 = st.columns(4)
    p1.write("Generator")
    p1.progress(min(1.0, generated / max(1, generated)), text="active" if generated else "waiting")
    p2.write("Detector")
    p2.progress(min(1.0, detected / max(1, generated)), text=f"{detected}/{generated}")
    p3.write("Alert queue")
    p3.progress(min(1.0, alert_backlog / max(1, alert_capacity)), text=f"{alert_backlog}/{alert_capacity}")
    p4.write("Orchestrator")
    orch_text = f"{orchestrated}/{alerts}" if alerts else "waiting"
    p4.progress(min(1.0, orchestrated / max(1, alerts)), text=orch_text)
    if orchestrator_failed:
        st.error(f"Orchestrator failures in this run: {orchestrator_failed}. Check the orchestrator terminal and the dead-letter topic.")

    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Detector queue wait", f"{detector_queue:.1f} ms" if detector_queue is not None else "–")
    l2.metric("Detector processing", f"{det_stage:.1f} ms")
    l3.metric("Orchestrator queue wait", f"{orchestrator_queue:.1f} ms" if orchestrator_queue is not None else "waiting")
    l4.metric("Orchestrator processing", f"{orch_stage:.1f} ms" if orchestrated else "waiting")

    chart_df = run_df[run_df.metric == "throughput_eps"].dropna(subset=["elapsed_s", "value"])
    if not chart_df.empty:
        st.markdown("**Recent stage throughput over elapsed time**")
        throughput_chart = chart_df.pivot_table(index="elapsed_s", columns="component", values="value", aggfunc="last")
        throughput_chart.index.name = "Elapsed seconds"
        st.line_chart(throughput_chart, use_container_width=True)

    backlog_rows = []
    counters = {"generated": 0.0, "detected": 0.0, "alerts": 0.0, "orchestrated": 0.0}
    for _, row in run_df.iterrows():
        key = (row.get("component"), row.get("metric"))
        if key == ("generator", "events_sent"):
            counters["generated"] = row["value"]
        elif key == ("detector", "events_processed"):
            counters["detected"] = row["value"]
        elif key == ("detector", "alerts_emitted"):
            counters["alerts"] = row["value"]
        elif key == ("orchestrator", "events_processed"):
            counters["orchestrated"] = row["value"]
        else:
            continue
        backlog_rows.append({
            "Elapsed seconds": row["elapsed_s"],
            "Ingress backlog": max(0.0, counters["generated"] - counters["detected"]),
            "Alert backlog": max(0.0, counters["alerts"] - counters["orchestrated"]),
        })
    if backlog_rows:
        st.markdown("**Estimated Kafka backlog over elapsed time**")
        backlog_df = pd.DataFrame(backlog_rows).groupby("Elapsed seconds", as_index=True).last()
        st.line_chart(backlog_df, use_container_width=True)

    latency_metrics = ["queue_wait_ms", "stage_latency_ms", "end_to_end_latency_ms"]
    latency_df = run_df[run_df.metric.isin(latency_metrics)].dropna(subset=["elapsed_s", "value"])
    latency_df = latency_df[(latency_df.value >= 0) & (latency_df.value <= 120000)]
    if not latency_df.empty:
        st.markdown("**Latency decomposition over elapsed time (milliseconds)**")
        latency_df = latency_df.assign(series=latency_df["component"] + ":" + latency_df["metric"])
        latency_chart = latency_df.pivot_table(index="elapsed_s", columns="series", values="value", aggfunc="mean")
        latency_chart.index.name = "Elapsed seconds"
        st.line_chart(latency_chart, use_container_width=True)

    if alerts and not orchestrator_received:
        st.warning("Alerts exist, but the orchestrator has not consumed any alert from this run. Restart agent_orchestrator.py from v0.3.3 before starting the telemetry generator and verify that it prints processed alerts.")
    elif orchestrator_received and not orchestrated:
        st.info("The orchestrator has received alerts and is processing them. Refresh the metrics shortly. High-load runs use deterministic XAI and batched Kafka publishing.")

    st.download_button(
        "Download Lab 2b metrics CSV",
        run_df.to_csv(index=False).encode("utf-8"),
        file_name=f"lab2b_{profile_name}_{latest_run[:8]}_metrics.csv",
        mime="text/csv",
    )
else:
    st.info("No high-load metrics yet. Start the pipeline and run, for example: python telemetry_generator.py --profile normal --events 500")
