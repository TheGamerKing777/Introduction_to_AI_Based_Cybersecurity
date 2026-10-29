# Laboratory 2b — High-Load Cybersecurity with Morpheus Lite

## Purpose

This laboratory extends Lab 2a from individual case investigation to pipeline survivability. You will operate the Morpheus Lite telemetry, detector, agent orchestrator, and dashboard under increasing event rates and use measured evidence to identify saturation, queue growth, latency, and recovery.

## Expected duration

120–150 minutes.

## Learning outcomes

After completing the laboratory, you should be able to:

1. distinguish baseline, normal, burst, sustained, and attack-surge load;
2. compare generator, detector, and orchestrator throughput;
3. identify the first saturated stage from utilization and backlog evidence;
4. separate queue-wait latency from stage-processing latency;
5. explain why latency can rise before total machine utilization reaches 100%;
6. evaluate the trade-off between early filtering and deeper analysis;
7. determine whether a pipeline is Normal, under High Load, or Overloaded;
8. export reproducible metrics and justify conclusions from them.

## Safety and conduct

- Use only the supplied synthetic telemetry.
- Do not connect Morpheus Lite to real organizational systems or data.
- Do not modify Kafka topics, queue capacities, or processing delays unless instructed.
- Keep each component in a separate terminal.
- Begin telemetry only after the detector is initialized and the orchestrator reports `ready` with an assigned partition.

## 1. Prepare the environment

Open Command Prompt in the project directory:

```cmd
cd "C:\Users\akoju\OneDrive - Holon Institute of Technology\Current Work\Projects\morpheus-lite"
.venv\Scripts\activate.bat
```

Verify the installation:

```cmd
python -m pytest -q
```

Expected result for the stable release:

```text
14 passed
```

## 2. Start the platform

Use a separate terminal for each component.

### Terminal 1 — Redpanda and Console

```cmd
docker compose up -d redpanda redpanda-console
docker compose ps
```

Both services must be running. Redpanda Console is available at:

```text
http://localhost:8080
```

### Terminal 2 — Detector

```cmd
cd "C:\Users\akoju\OneDrive - Holon Institute of Technology\Current Work\Projects\morpheus-lite"
.venv\Scripts\activate.bat
python morpheus_lite_detector.py
```

Wait for:

```text
Isolation Forest and user fingerprinting initialized
```

### Terminal 3 — Agent orchestrator

```cmd
cd "C:\Users\akoju\OneDrive - Holon Institute of Technology\Current Work\Projects\morpheus-lite"
.venv\Scripts\activate.bat
python agent_orchestrator.py
```

Wait for a readiness message similar to:

```text
Agent orchestrator ready on morpheus.alerts [group=agent-orchestrator-..., partitions=morpheus.alerts:0]
```

Do not start telemetry before this message appears.

### Terminal 4 — Dashboard

```cmd
cd "C:\Users\akoju\OneDrive - Holon Institute of Technology\Current Work\Projects\morpheus-lite"
.venv\Scripts\activate.bat
python -m streamlit run dashboard.py
```

Open:

```text
http://localhost:8501
```

## 3. Clean experiment procedure

Before a new graded experiment, stop the detector, orchestrator, dashboard, and generator with `Ctrl+C`. Keep Redpanda running. Delete only the old high-load metrics file:

```cmd
del data\high_load_metrics.jsonl
```

Do not delete `audit.jsonl` or `fingerprint_profiles.json`.

Restart the detector, orchestrator, and dashboard in the order shown above. Confirm that the dashboard displays a new `run_id` after telemetry begins.

## 4. Experiments

For each experiment:

1. run the profile in a fifth terminal;
2. wait for the generator to finish;
3. allow the downstream stages to drain;
4. select **Refresh high-load metrics**;
5. record the required measurements;
6. download the metrics CSV before starting the next profile.

### Experiment A — Baseline

```cmd
python telemetry_generator.py --profile baseline --events 120
```

Expected pattern: low utilization, no persistent backlog, and stable latency.

### Experiment B — Normal operational load

```cmd
python telemetry_generator.py --profile normal --events 500
```

Expected pattern: similar stage throughput, temporary small queues, and complete end-to-end processing. A verified reference run processed all 500 generated events through the detector and orchestrator, with empty final backlogs and approximately 80 ms full-pipeline latency.

### Experiment C — Burst load

```cmd
python telemetry_generator.py --profile burst --events 2000
```

Expected pattern: rapid queue growth during a burst followed by queue drainage during the pause. Explain how buffering decouples production from analysis.

### Experiment D — Sustained high load

```cmd
python telemetry_generator.py --profile sustained --events 5000
```

Expected pattern: one or more downstream stages process more slowly than the generator, causing persistent or increasing backlog.

### Experiment E — Adversarial attack surge

```cmd
python telemetry_generator.py --profile attack_surge --events 5000
```

This profile combines high event volume with a higher suspicious-event probability. More events therefore reach expensive downstream analysis. Expect greater orchestrator pressure than under a normal profile with the same event count.

## 5. Measurements to record

Complete this table for each assigned profile:

| Measure | Value |
|---|---|
| Run ID | |
| Generated events/s | |
| Detector events/s | |
| Orchestrator alerts/s | |
| Detector utilization | |
| Orchestrator utilization | |
| Peak ingress backlog / capacity | |
| Peak alert backlog / capacity | |
| Detector queue wait | |
| Detector processing latency | |
| Orchestrator queue wait | |
| Orchestrator processing latency | |
| Full-pipeline E2E latency | |
| Final system status | |
| Generated / Detected / Orchestrated | |

## 6. Interpreting the dashboard

- **Throughput alignment:** a stable pipeline has similar generator, detector, and orchestrator rates over time.
- **Backlog:** increasing backlog means an upstream stage is producing faster than the downstream stage can consume.
- **Queue wait:** time spent waiting before processing; this often dominates under overload.
- **Processing latency:** time used by the stage itself.
- **Full-pipeline E2E latency:** total time from event generation to orchestration completion.
- **Utilization:** an estimate of how close each stage is to its configured safe capacity.
- **System status:** combines utilization and backlog thresholds into Normal, High Load, or Overloaded.

## 7. Troubleshooting checkpoints

### Orchestrator remains at zero

Confirm that its terminal shows the `ready` message and an assigned partition. Restart the orchestrator before starting the generator. A unique consumer group is created for each process.

### Alerts exist but no orchestrated results appear

Check the orchestrator terminal for processing or error messages. Confirm that `config/settings.yaml` contains:

```yaml
high_load:
  lab_xai_provider: deterministic
```

### Old measurements appear

Stop the active components and delete:

```cmd
del data\high_load_metrics.jsonl
```

Restart the components and verify that the dashboard shows a new `run_id`.

### Dashboard shows historical SOC cases

This is normal because Lab 2a audit data is retained. Lab 2b metrics are isolated by the latest high-load `run_id`.

## 8. Required evidence

Submit:

- the downloaded `lab2b_high_load_metrics.csv`;
- one throughput screenshot;
- one backlog screenshot;
- one latency-decomposition screenshot;
- the completed measurement table;
- a short answer identifying the bottleneck for each assigned profile;
- a 300–500 word reflection.

## 9. Reflection questions

1. Which stage saturated first, and what evidence supports your conclusion?
2. Did queue wait or processing time contribute more to total latency?
3. Why can latency rise even when the machine is not at 100% CPU utilization?
4. Why does the attack-surge profile stress the orchestrator more than a normal profile with the same event count?
5. When is early filtering beneficial, and what security risk can overly aggressive filtering create?
6. Is graceful degradation preferable to attempting full analysis of every event? Justify your answer.
7. Which metric would you use to trigger backpressure, and why?

## Stable release note

This guide targets Morpheus Lite v0.3.4. High-load runs use deterministic XAI by default so that the orchestration stage can be measured reproducibly without local Llama latency becoming an unintended bottleneck. Lab 2a may continue to use Ollama/Llama when assigned.
