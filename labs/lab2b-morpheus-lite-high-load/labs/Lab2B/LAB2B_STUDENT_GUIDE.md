# Morpheus Lite v0.3.4 — Laboratory 2b Student Guide
## High-Load Cybersecurity and Evidence-Based Performance Analysis

## Purpose

In this laboratory, you operate an AI-native SOC pipeline under controlled workload profiles. You will observe system behavior, export quantitative measurements, and use those measurements to identify bottlenecks and justify engineering decisions.

The dashboard is used for live observation. The **downloaded CSV is the central laboratory artifact and primary evidence source**.

## Learning outcomes

After completing the laboratory, you should be able to:

1. operate the Morpheus Lite streaming pipeline;
2. distinguish throughput, utilization, backlog, queue waiting time, processing time, and end-to-end latency;
3. identify a pipeline bottleneck using quantitative evidence;
4. determine whether a queue grows, stabilizes, or drains;
5. compare normal and high-load behavior;
6. justify an engineering recommendation using exported measurements.

## Safety and conduct

- Use only the supplied synthetic telemetry.
- Do not connect the platform to real organizational systems.
- Do not enter personal, confidential, or operational security information.
- Treat AI-generated recommendations as advisory.
- Do not submit internal JSONL runtime files.

## 1. Prepare the environment

Open Command Prompt in the project root and activate the virtual environment:

```cmd
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

Use a separate Command Prompt window for each component.

### Terminal 1 — Redpanda

```cmd
docker compose up -d redpanda redpanda-console
docker compose ps
```

### Terminal 2 — Detector

```cmd
.venv\Scripts\activate.bat
python morpheus_lite_detector.py
```

Wait for:

```text
Isolation Forest and user fingerprinting initialized
```

### Terminal 3 — Orchestrator

```cmd
.venv\Scripts\activate.bat
python agent_orchestrator.py
```

Wait for the READY message showing a unique consumer group and assigned partition.

### Terminal 4 — Dashboard

```cmd
.venv\Scripts\activate.bat
python -m streamlit run dashboard.py
```

Open `http://localhost:8501`.

## 3. Start a clean experiment

Stop old detector, orchestrator, dashboard, and generator processes before a new graded run. Keep Redpanda running.

Delete old high-load metrics:

```cmd
del data\high_load_metrics.jsonl
```

Restart the detector, orchestrator, and dashboard in that order.

## 4. Run the assigned workload profile

Open a fifth terminal, activate the environment, and run the profile assigned by the instructor.

```cmd
python telemetry_generator.py --profile normal --events 500
```

Other available profiles include:

```cmd
python telemetry_generator.py --profile burst --events 2000
python telemetry_generator.py --profile sustained --events 3000
python telemetry_generator.py --profile attack_surge --events 5000
```

Do not start the generator until the detector is initialized and the orchestrator displays its READY message.

## 5. Observe the dashboard

Record the live behavior of:

- generator, detector, and orchestrator throughput;
- detector and orchestrator utilization;
- alert backlog and queue capacity;
- queue waiting time;
- stage processing time;
- full-pipeline end-to-end latency;
- pipeline health status.

Take one screenshot that clearly shows the experiment profile, run ID, and Lab 2b observability metrics.

## 6. Download the CSV — Required

After the experiment completes and the orchestrator has processed the alerts:

1. Click **Download CSV** in the Lab 2b dashboard.
2. Save the file as:

```text
Lab2B_<StudentID>_<Profile>.csv
```

Example:

```text
Lab2B_123456789_attack_surge.csv
```

3. Open the CSV and verify that it belongs to your current `run_id` and workload profile.
4. Confirm that it contains throughput, utilization, backlog, and latency measurements.

The CSV is not optional. It is the primary quantitative evidence for the laboratory report.

## 7. Analyze the CSV

Use Excel, LibreOffice Calc, or pandas. Do not analyze `audit.jsonl` or `high_load_metrics.jsonl` directly.

Complete the following summary table:

| Metric | Measured value |
|---|---:|
| Average generator throughput | |
| Average detector throughput | |
| Average orchestrator throughput | |
| Maximum alert backlog | |
| Average detector utilization | |
| Average orchestrator utilization | |
| Mean detector queue waiting time | |
| Mean detector processing time | |
| Mean orchestrator queue waiting time | |
| Mean orchestrator processing time | |
| Mean full-pipeline E2E latency | |

Create at least two charts from the CSV:

1. throughput by pipeline stage over elapsed time;
2. alert backlog or end-to-end latency over elapsed time.

## 8. Engineering analysis

Answer the following using specific CSV values:

1. Which component was the bottleneck?
2. What quantitative evidence supports that conclusion?
3. Did the alert backlog grow, stabilize, or drain?
4. Was latency dominated by queue waiting or stage processing?
5. Did the orchestrator keep pace with the detector?
6. Which metric gave the earliest warning of overload?
7. Which component would you optimize first, and why?
8. How would the selected profile differ from normal operation?

## 9. Required submission

Submit one ZIP file named:

```text
Lab2B_<StudentID>_<Profile>.zip
```

It must contain:

```text
Lab2B_<StudentID>_<Profile>.csv
Lab2B_<StudentID>_<Profile>_dashboard.png
Lab2B_<StudentID>_<Profile>_analysis.pdf
reflection.md
```

The 1–2 page analysis must include the completed summary table, at least two charts, and evidence-based answers to the engineering questions.

## 10. Reflection

In `reflection.md`, briefly answer:

- What did the dashboard suggest initially?
- What did the CSV confirm or contradict?
- Which conclusion depended most strongly on quantitative evidence?
- What would you change in the architecture?
