# Morpheus Lite v0.3.4 — Stable Lab 2b Validation Record

## Release decision

Morpheus Lite v0.3.4 is frozen as the stable functional baseline for Laboratory 2b. No cosmetic dashboard changes are included in this release.

## Automated verification

Command:

```text
python -m pytest -q
```

Result:

```text
14 passed
```

## Verified live normal-load run

A live Windows/Redpanda run was completed with:

```text
python telemetry_generator.py --profile normal --events 500
```

Observed completion evidence:

- Generated: 500
- Detected: 500
- Alerts: 500
- Orchestrator received: 500
- Orchestrated: 500
- Generator throughput: 25.0 events/s
- Detector throughput: 25.1 events/s
- Orchestrator throughput: 24.7 alerts/s
- Final ingress backlog: 0 / 500
- Final alert backlog: 0 / 500
- Detector utilization: 71.9%
- Orchestrator utilization: 65.5%
- Detector queue wait: 17.7 ms
- Detector processing: 28.6 ms
- Orchestrator queue wait: 11.2 ms
- Orchestrator processing: 26.5 ms
- Full-pipeline E2E latency: 80.7 ms

This confirms end-to-end event flow, queue drainage, throughput alignment, latency decomposition, and orchestrator Kafka consumption.

## Additional attack-surge profile validation

The profile configuration and pacing logic were exercised offline for 1,000 events because the build environment used for release packaging does not provide Docker/Redpanda. Results are stored in:

```text
docs/validation/attack_surge_offline_validation.csv
```

Observed:

- configured rate: 500 events/s;
- burst size: 500;
- burst interval: 1 second;
- configured suspicious-event probability: 0.65;
- observed suspicious events: 667 / 1,000;
- effective generation rate: approximately 499.8 events/s.

This validates the profile configuration and pacing behavior, but it is not a substitute for the final live Kafka end-to-end attack-surge run on the instructor machine.

## Final live acceptance check

Before student release, run:

```text
python telemetry_generator.py --profile attack_surge --events 5000
```

Accept the release when:

1. the detector and orchestrator remain running;
2. `Orchestrator received` and `Orchestrated` increase;
3. the dashboard shows the current run ID;
4. backlogs and latency are plotted without invalid values;
5. the CSV export downloads successfully.
