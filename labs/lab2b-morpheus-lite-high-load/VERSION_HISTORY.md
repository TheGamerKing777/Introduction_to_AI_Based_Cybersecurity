# Version 0.3.4

- Fixed orchestrator non-consumption caused by competing/stale fixed consumer groups.
- Each orchestrator process now uses a unique Kafka consumer group and client id.
- Added an explicit partition-assignment readiness check before telemetry may start.
- Startup output now reports the topic, group id, and assigned partitions.
- Added clear startup failure diagnostics when Redpanda or the topic is unavailable.

# Version 0.3.3

- Batched Kafka publishing in the orchestrator to remove per-topic flush bottlenecks.
- Added orchestrator received and failed counters.
- Added pipeline-health progress indicators and clearer diagnostics.

# Version 0.3.2 — High-Load Metrics Correction

- uses deterministic XAI for high-load experiment runs so orchestration metrics remain observable;
- records detector and orchestrator queue-wait latency separately from processing latency;
- reports full-pipeline latency only after orchestration completes;
- adds queue capacities and Normal / High Load / Overloaded status;
- changes chart axes to elapsed seconds;
- adds orchestrated counters and latency decomposition.

# Version 0.3.1 - High-Load Metrics Correction

- Replaced cross-process monotonic timestamps with wall-clock epoch timestamps for valid end-to-end latency.
- Added per-run identifiers so the dashboard isolates the latest experiment.
- Replaced lifetime-average throughput with a five-second rolling throughput rate.
- Added ingress and alert backlog estimates, stage-utilization indicators, and explicit generated/detected/alert counts.
- Added corrected latency filtering and per-run CSV export.
- Added automated tests for rolling rate and wall-clock timestamps.

# Version History

## Morpheus Lite Laboratory 1.0.0 - 2026-07-25

Release type: Stable educational and research laboratory baseline.

### Major capabilities

- Redpanda/Kafka streaming pipeline
- Synthetic cybersecurity telemetry
- Isolation Forest and rule-based detection
- User behavioral fingerprinting
- Threat Hunter investigation
- Responsible AI policy gating
- Multi-provider XAI with resilient fallback
- Meta-AI supervisory review
- Human decision workflow
- Evidence-based justification capture
- JSONL and optional Parquet research storage
- Prometheus-compatible observability
- Dead-letter topic
- Automated tests

### Dashboard stabilization

- Added shared `selected_alert_id` session state.
- Synchronized All Cases, Human Decision Queue, and Case Details.
- Added explicit first-column case selection.
- Preserved `alert_id` as the visible case key.
- Displayed `correlation_id` for backend traceability.

### Documentation

- Updated main README.
- Added architecture guide.
- Added student laboratory guide.
- Added instructor quick start.
- Added laboratory release manifest.
- Added research data guide.
- Added troubleshooting guide.
- Updated migration guide and run-order reference.

### Freeze policy

New capabilities are deferred to later versions. Only backward-compatible maintenance fixes should be applied to v1.0.

## 0.2.0

- Added configurable Kafka topics and policies.
- Added deterministic, Ollama, NIM, ONNX Runtime, and Triton inference providers.
- Added resilient deterministic fallback and provider telemetry.
- Added user-specific digital fingerprinting.
- Added Meta-AI supervisory review.
- Added human decision workflow.
- Added JSONL and Parquet research storage.
- Added Prometheus metrics, dead-letter events, Compose profiles, and tests.

## 0.1.0

Original prototype with Redpanda, synthetic telemetry, Isolation Forest, Threat Hunter, RAI policy, Ollama XAI, and a Streamlit dashboard.

## 0.3.0 — Lab 2b High-Load Extension

- Added configurable telemetry load profiles: baseline, normal, burst, sustained, and attack surge.
- Added event-rate and attack-probability command-line controls.
- Added JSONL high-load metrics for generator, detector, and orchestrator throughput and latency.
- Added configurable simulated detector and orchestrator processing costs.
- Added a Lab 2b high-load observability section to the Streamlit dashboard.
- Added CSV export and automated tests for the high-load extension.
- Added `docs/LAB_2B_HIGH_LOAD_STUDENT_GUIDE.md`.
