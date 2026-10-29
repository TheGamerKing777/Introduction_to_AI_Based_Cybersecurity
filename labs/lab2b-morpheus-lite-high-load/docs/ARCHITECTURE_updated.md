# Morpheus Lite Laboratory Architecture

## 1. Purpose

Morpheus Lite Laboratory models an AI-assisted SOC workflow while preserving human authority over consequential decisions. It is designed for education, controlled experimentation, and research on human-AI collaboration.

## 2. End-to-end architecture

```text
+----------------------+      +--------------------+
| Telemetry Generator  | ---> | Redpanda / Kafka   |
+----------------------+      +--------------------+
                                      |
                                      v
                            +-----------------------+
                            | AI Detector           |
                            | - Isolation Forest    |
                            | - Rules               |
                            | - Fingerprinting      |
                            +-----------------------+
                                      |
                                      v
                            +-----------------------+
                            | Agent Orchestrator    |
                            | 1. Threat Hunter      |
                            | 2. RAI Policy         |
                            | 3. XAI Provider       |
                            | 4. Meta-AI Review     |
                            +-----------------------+
                                      |
                    +-----------------+------------------+
                    |                                    |
                    v                                    v
          +----------------------+             +----------------------+
          | Streamlit Dashboard  |             | Audit / Research     |
          | Human Decision       |             | JSONL / Parquet      |
          +----------------------+             +----------------------+
```

The agent layer uses **orchestrator-mediated, sequential collaboration**. Agents do not engage in unrestricted peer-to-peer conversation. Instead, the orchestrator invokes each agent in a defined order, validates the returned structure, and passes the relevant output to the next stage.

## 3. Agent-to-agent and data handoff flow

```text
morpheus.alerts
      |
      v
+-----------------------+
| Agent Orchestrator    |
+-----------------------+
      |
      | alert
      v
+-----------------------+
| Threat Hunter Agent   |
| Input: alert          |
| Output: investigation |
+-----------------------+
      |
      | alert + investigation
      v
+-----------------------+
| RAI Policy Agent      |
| Output: policy result |
+-----------------------+
      |
      | alert + investigation + policy result
      v
+-----------------------+
| XAI Agent / Provider  |
| Output: explanation   |
+-----------------------+
      |
      | complete case package
      v
+-----------------------+
| Meta-AI Supervisor    |
| Output: review result |
+-----------------------+
      |
      v
+-----------------------+
| Human Analyst         |
| Final authority       |
+-----------------------+
```

### 3.1 Handoff contract

| Stage | Receives | Produces | Primary purpose |
|---|---|---|---|
| Threat Hunter | Detector alert | Investigation findings, evidence summary, MITRE ATT&CK interpretation | Establish the security meaning of the alert |
| RAI Policy | Alert and investigation | Permission status, recommended action, approval requirement, policy note | Apply governance and action constraints |
| XAI Agent | Alert, investigation, and RAI result | Plain-language explanation, evidence summary, uncertainty, recommended next step | Make the case understandable to the analyst |
| Meta-AI Supervisor | Complete case package | Approval, challenge, evidence request, or escalation | Assess whether the AI-supported reasoning is sufficient |
| Human Analyst | Full case and Meta-AI review | Approve, reject, escalate, request more evidence, or defer | Exercise final decision authority |

Each handoff should preserve `alert_id`, `correlation_id`, provenance, provider metadata, and processing status. A downstream agent should not silently overwrite upstream evidence; it should add its own structured result to the case package.

### 3.2 Orchestration model

The current implementation is a controlled pipeline rather than a free-form multi-agent dialogue:

1. The orchestrator consumes an alert from `morpheus.alerts`.
2. It invokes the Threat Hunter and stores the investigation result.
3. It invokes the RAI Policy Agent using the alert and investigation.
4. It invokes the XAI provider using the alert, investigation, and RAI result.
5. It invokes the Meta-AI Supervisor using the complete case package.
6. It publishes the resulting records to their relevant Kafka topics and exposes the combined case to the dashboard.
7. The human analyst makes the final decision.

This design improves reproducibility, auditability, and classroom control because the order of reasoning and the source of every output remain explicit.

### 3.3 LLM boundary

The XAI Agent is the component that directly uses an LLM when an external or local inference provider is enabled. It receives structured case context and generates a natural-language explanation. The Threat Hunter, RAI Policy Agent, and Meta-AI Supervisor may operate deterministically in the reference laboratory mode.

LLM inference does not change the model weights during case processing. Morpheus Lite uses inference-time context rather than on-the-fly training. If the selected provider is unavailable, the XAI stage uses the configured fallback response so the pipeline can continue.

## 4. Component responsibilities

### Telemetry generator

Produces synthetic events representing login activity, process activity, network traffic, geographic context, and timestamps. It publishes to `raw.logs`.

### Detector

Consumes `raw.logs`, extracts numerical features, applies anomaly detection and policy rules, calculates risk, and publishes alerts to `morpheus.alerts`.

### Behavioral fingerprinting

Maintains user-specific behavioral profiles and compares new events with historical patterns. The output augments generic anomaly detection and provides a behavioral deviation score.

### Agent orchestrator

Coordinates the ordered execution of the Threat Hunter, RAI Policy, XAI, and Meta-AI stages. It assembles the combined case, preserves identifiers and provenance, applies fallback handling, and publishes stage outputs.

### Threat Hunter

Adds security findings, evidence summaries, and MITRE ATT&CK-oriented interpretation.

### RAI Policy

Constrains automated action. It determines whether a recommendation is permitted and whether human approval is mandatory.

### XAI provider

Generates a plain-language explanation using the configured provider. The inference abstraction supports deterministic, Ollama, NIM, ONNX Runtime, and Triton providers, with fallback behavior.

### Meta-AI supervisor

Reviews the quality and sufficiency of the AI-supported case. It can approve the reasoning, challenge it, request more evidence, or escalate it for human attention.

### Dashboard

Displays alerts, cases, evidence, RAI decisions, Meta-AI assessments, and human-decision controls. All panels use one shared selection state:

```python
st.session_state.selected_alert_id
```

### Audit and research storage

Records decisions and process evidence in append-only JSONL and optional Parquet outputs.

## 5. Identifier model

### `alert_id`

The unique case identifier used for dashboard synchronization and human review.

### `correlation_id`

The trace identifier used to connect records produced by different services and Kafka topics.

A single alert should preserve the same `correlation_id` as it passes through investigation, explanation, RAI, Meta-AI, and human-decision stages.

## 6. Dashboard synchronization

```text
All Cases selection
        |
        v
selected_alert_id
   |          |
   v          v
Decision     Case
Queue        Details
```

The leftmost **Select** checkbox in the editable cases table changes `selected_alert_id`. The active alert, decision queue, and case details are then rendered from the same identifier.

## 7. Data flow by topic

| Stage | Input | Output |
|---|---|---|
| Telemetry | synthetic generator | `raw.logs` |
| Detection | `raw.logs` | `morpheus.alerts` |
| Investigation | `morpheus.alerts` | `agent.investigations` |
| Explanation | alert, investigation, and RAI context | `agent.explanations` |
| Governance | alert and investigation | `audit.rai` |
| Meta-AI | combined case package | `agent.meta_ai` |
| Human decision | dashboard case | `human.decisions` |
| Failure handling | processing error | `dead.letter.events` |

Kafka topics provide event transport and persistence between platform stages. Within the current orchestrator process, the Threat Hunter, RAI, XAI, and Meta-AI functions are called sequentially; topic outputs make their results observable and available to downstream services, dashboards, audit tools, and research exporters.

## 8. Safety boundaries

- Only synthetic or approved teaching data should be used.
- The platform must not execute destructive security actions.
- High-impact recommendations remain subject to human review.
- The laboratory should run in an isolated environment.
- API keys must be supplied through environment variables, not committed files.
- LLM output must be treated as advisory and must remain subject to evidence review, RAI constraints, Meta-AI assessment, and human decision.

## 9. Frozen v1.0 interfaces

The following interfaces should remain backward compatible in the frozen laboratory release:

- Kafka topic names in `config/topics.yaml`;
- `alert_id` and `correlation_id` semantics;
- human-decision values;
- audit record fields;
- root-level startup commands;
- dashboard selection behavior;
- the ordered handoff sequence from Threat Hunter through Meta-AI review.
