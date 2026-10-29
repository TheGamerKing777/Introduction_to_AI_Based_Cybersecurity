# Lab 1a — Raw Security Logs to MITRE ATT&CK

This project demonstrates a simple, transparent cybersecurity analysis workflow:

```text
Raw security log
        ↓
Rule-based detector
        ↓
Candidate security findings
        ↓
MITRE ATT&CK STIX enrichment
        ↓
Local SOC dashboard
```

The laboratory runs locally with Docker Desktop. It does **not** require a cloud account, API key, LLM, AI agent, Kali Linux, Nmap, DVWA, a vulnerable machine, or real attack execution.

## Requirements

- Windows PowerShell
- Docker Desktop
- Docker Compose v2
- A browser

## Project services

The current Docker Compose project contains three services:

| Service | Role | Default behavior |
|---|---|---|
| `detector` | Reads `logs/security.log`, applies rules, writes `output/findings.json` | Rescans every 5 seconds |
| `dashboard` | Displays findings, MITRE metadata, evidence, and raw logs | Available at `http://localhost:8000` |
| `simulator` | Appends synthetic events to the log | Optional; runs only with the `simulation` profile |

The detector is deterministic and rule-based. It is **not** an AI or LLM system.

## MITRE ATT&CK techniques used

| Observed pattern | MITRE ATT&CK technique | Tactic |
|---|---|---|
| At least 3 failed-password events from the same source IP | **T1110 — Brute Force** | Credential Access |
| A log line containing `Network scan detected` | **T1046 — Network Service Discovery** | Discovery |

A detection finding is **not proof that an attack occurred**. It is a rule-based interpretation of observable evidence.

## Clean baseline log

The repository includes a tracked starter file:

```text
logs/security.log
```

The clean baseline contains six records:

```text
2026-07-11T09:00:10 INFO User student logged in successfully from 172.18.0.10
2026-07-11T09:02:11 WARN Failed password for root from 172.18.0.5 port 44231 ssh2
2026-07-11T09:02:14 WARN Failed password for root from 172.18.0.5 port 44232 ssh2
2026-07-11T09:02:18 WARN Failed password for root from 172.18.0.5 port 44233 ssh2
2026-07-11T09:04:20 INFO Network scan detected from 172.18.0.7 against ports 22,80,443,3306
2026-07-11T09:07:33 INFO User administrator logged out
```

With this clean baseline, the dashboard should show:

- **2 total findings**
- **1 High** — T1110 Brute Force
- **1 Medium** — T1046 Network Service Discovery

## Start the lab

Open PowerShell in this directory.

Verify Docker:

```powershell
docker version
docker compose config
```

Start the detector and dashboard:

```powershell
docker compose up --build -d
```

Check the services:

```powershell
docker compose ps
```

Open:

```text
http://localhost:8000
```

Alternatively:

```powershell
.\run_lab.ps1
```

## Continuous rescanning

The detector runs continuously and rescans the log every 5 seconds.

After editing `logs/security.log`, you normally **do not need to restart Docker**. Save the file, wait at least 5 seconds, and refresh the dashboard if necessary.

## Controlled student experiments

Before experimenting:

```powershell
Copy-Item .\logs\security.log .\logs\security.log.bak
```

### Experiment A — Below threshold

Keep only two failed-password records from `172.18.0.5`.

Expected:
- T1110 disappears
- T1046 remains
- total findings becomes 1

### Experiment B — Three failures from different IPs

Create three failed-password records, each from a different source IP.

Expected:
- no T1110 finding for any individual IP

### Experiment C — Threshold crossing

Append three failed-password records from one new IP, e.g. `192.0.2.55`.

Expected:
- a new T1110 finding appears

### Experiment D — Add another scan

Append:

```text
2026-10-22T10:02:00Z INFO Network scan detected from 192.0.2.77 against ports 22,80,443
```

Expected:
- a new T1046 finding appears

## Optional simulator

Run only after the controlled experiments:

```powershell
docker compose --profile simulation up --build -d
docker compose logs --tail=20 simulator
```

Stop it before final evidence collection:

```powershell
docker compose stop simulator
```

The simulator is synthetic and nondeterministic, so finding counts can change continuously.

## MITRE ATT&CK knowledge

The detector resolves candidate IDs using:

```text
mitre/enterprise-attack-mini.json
```

Optional full Enterprise ATT&CK download:

```powershell
.\download_attack_data.ps1
```

## Restore and stop

Restore the clean log:

```powershell
Copy-Item .\logs\security.log.bak .\logs\security.log -Force
```

Stop the lab:

```powershell
docker compose --profile simulation down
```

## Important interpretation rule

MITRE ATT&CK mapping provides a standard vocabulary for describing behavior. It does **not** establish attacker identity, malicious intent, successful compromise, or complete incident context.
