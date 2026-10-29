# Laboratory 1a

## Raw Security Logs → Rule-Based Detection → MITRE ATT&CK → SOC Dashboard

**Student handout | 60 minutes | Individual or pairs | Windows PowerShell + Docker Desktop**

Repository: https://github.com/melofon/HIT-ai-cybersecurity-labs/tree/main/labs/lab1a-mitre-soc

# 1. Learning objectives

By the end of this laboratory, you should be able to:

1. Run the supplied detector and SOC dashboard using Docker Compose.
2. Inspect raw `security.log` records and explain how detection rules operate.
3. Distinguish T1110 Brute Force and T1046 Network Service Discovery from confirmed attacks.
4. Verify technique metadata using the bundled MITRE ATT&CK STIX knowledge file.
5. Explain why repeated events must be interpreted by source and context.
6. Observe how changing raw logs changes detector output.
7. Use an optional simulator to observe continuously changing synthetic telemetry.
8. Document reproducible observations, uncertainty, and the limitations of simple rules.

# 2. Actual project architecture

This laboratory uses the supplied GitHub project.

It does **not** require Kali Linux, DVWA, Nmap, a vulnerable target, cloud services, an LLM, or an AI agent.

| Service | Role | Relevant behavior |
|---|---|---|
| `detector` | Reads logs and writes `findings.json` | Rescans every 5 seconds |
| `dashboard` | Displays findings and raw logs | `http://localhost:8000` |
| `simulator` | Appends synthetic events | Optional Compose profile; ~10-second interval |

Data flow:

```text
logs/security.log
        ↓
detector rules
        ↓
candidate MITRE technique ID
        ↓
local MITRE STIX lookup
        ↓
output/findings.json
        ↓
SOC dashboard
```

The detector is deterministic and rule-based, not an AI/LLM system.

# 3. Prerequisites and safety

Required:

- Docker Desktop running
- Docker Compose v2
- Windows PowerShell
- Browser
- Local copy of the complete project folder

Safety rules:

- Use only supplied or synthetic log records.
- Do not scan real networks or HIT infrastructure.
- Do not use real passwords or personal data.
- Keep the optional simulator stopped until the final activity.
- Back up the clean baseline before experiments.

# 4. Clean baseline

The repository includes:

```text
logs/security.log
```

It should initially contain exactly:

```text
2026-07-11T09:00:10 INFO User student logged in successfully from 172.18.0.10
2026-07-11T09:02:11 WARN Failed password for root from 172.18.0.5 port 44231 ssh2
2026-07-11T09:02:14 WARN Failed password for root from 172.18.0.5 port 44232 ssh2
2026-07-11T09:02:18 WARN Failed password for root from 172.18.0.5 port 44233 ssh2
2026-07-11T09:04:20 INFO Network scan detected from 172.18.0.7 against ports 22,80,443,3306
2026-07-11T09:07:33 INFO User administrator logged out
```

Expected initial dashboard:

- Total findings: **2**
- High: **1**
- Medium: **1**
- T1110 from `172.18.0.5`
- T1046 from `172.18.0.7`

# 5. Setup and verification — 10 minutes

```powershell
docker version
docker compose config
docker compose up --build -d
docker compose ps
```

Open:

```text
http://localhost:8000
```

Inspect logs:

```powershell
docker compose logs --tail=30 detector
docker compose logs --tail=30 dashboard
```

Inspect findings:

```powershell
Get-Content .\output\findings.json
```

Important: the detector rescans automatically every 5 seconds. You do not need to restart Docker after ordinary log edits.

# 6. Activity A — Inspect evidence — 10 minutes

Open:

```text
logs/security.log
output/findings.json
```

Record:
- `finding_count`
- source IPs
- MITRE technique IDs
- severity
- evidence
- lookup status

Trace each baseline finding back to the exact raw log record.

# 7. Activity B — Understand the rules — 10 minutes

## T1110

The detector counts lines containing `Failed password` by source IP.

Three or more failures from the **same source IP** produce a High-severity candidate T1110 finding.

Default threshold:

```text
FAILED_PASSWORD_THRESHOLD=3
```

There is no time window.

## T1046

Any line containing `Network scan detected` produces a Medium-severity candidate T1046 finding.

Inspect `detector.py` and identify:
- `FAILED_PASSWORD_THRESHOLD`
- `SCAN_INTERVAL_SECONDS`
- source-IP extraction
- candidate technique assignment

Explain why a rule match is not the same as confirmed attacker intent.

# 8. Activity C — Controlled changes and rescanning — 15 minutes

Back up the baseline:

```powershell
Copy-Item .\logs\security.log .\logs\security.log.bak
```

Ensure the simulator is stopped:

```powershell
docker compose stop simulator
```

After each change: save, wait at least 5 seconds, refresh the dashboard, and compare predicted vs actual results.

## C1 — Below threshold

Remove one of the three failed-password lines for `172.18.0.5`.

Expected:
- T1110 disappears
- T1046 remains
- total findings becomes 1

## C2 — Three failures from three different IPs

Example:

```text
2026-10-22T10:00:00Z WARN Failed password for test from 192.0.2.51 port 40001 ssh2
2026-10-22T10:00:02Z WARN Failed password for test from 192.0.2.52 port 40002 ssh2
2026-10-22T10:00:04Z WARN Failed password for test from 192.0.2.53 port 40003 ssh2
```

Expected:
- no T1110 for these three records

## C3 — Threshold crossing

Append:

```text
2026-10-22T10:01:00Z WARN Failed password for test from 192.0.2.55 port 40001 ssh2
2026-10-22T10:01:02Z WARN Failed password for test from 192.0.2.55 port 40002 ssh2
2026-10-22T10:01:04Z WARN Failed password for test from 192.0.2.55 port 40003 ssh2
```

Expected:
- new T1110 for `192.0.2.55`

## C4 — Add another scan

Append:

```text
2026-10-22T10:02:00Z INFO Network scan detected from 192.0.2.77 against ports 22,80,443
```

Expected:
- new T1046 finding

# 9. Activity D — MITRE knowledge and optional simulator — 10 minutes

Inspect:

```text
mitre/enterprise-attack-mini.json
```

The detector enriches candidate IDs with technique names, tactics, URLs, descriptions, and STIX metadata.

Optional full Enterprise ATT&CK download:

```powershell
.\download_attack_data.ps1
```

Then start the simulator:

```powershell
docker compose --profile simulation up --build -d
docker compose logs --tail=20 simulator
```

Observe changing logs and finding counts.

The simulator is synthetic and nondeterministic.

Stop it before final evidence collection:

```powershell
docker compose stop simulator
```

# 10. Deliverable and cleanup — 5 minutes

Submit one PDF or TXT report with:

1. Docker verification and dashboard screenshot.
2. Initial clean-baseline finding count.
3. Final finding count before simulator use.
4. A two-row evidence → rule → technique → tactic → uncertainty table.
5. Results of C1–C4: changed lines, predicted result, actual result, explanation.
6. A 100–150 word SOC narrative distinguishing facts, rule-based interpretation, and uncertainty.

Restore the clean baseline:

```powershell
Copy-Item .\logs\security.log.bak .\logs\security.log -Force
```

Stop the lab:

```powershell
docker compose --profile simulation down
```

# 11. Troubleshooting

| Symptom | Check |
|---|---|
| Docker client works but no server section | Start Docker Desktop |
| Dashboard does not load | `docker compose ps`, dashboard logs, port 8000 |
| No `findings.json` | Detector logs, output directory, wait for scan |
| No new findings | Log path, exact trigger text, source-IP grouping |
| MITRE lookup missing | `mitre/enterprise-attack-mini.json` and volume mount |
| Counts keep changing | Stop the simulator |
| Many findings appear at startup | Restore the clean six-line baseline |

# 12. Key interpretation rule

MITRE ATT&CK mapping identifies behavior consistent with a technique. It does not establish attacker identity, intent, successful compromise, or complete incident context.
