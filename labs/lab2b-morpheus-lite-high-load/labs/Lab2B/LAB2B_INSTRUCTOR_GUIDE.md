# Laboratory 2b Instructor Guide

## Central assessment principle

The exported CSV is the primary evidence artifact. A dashboard screenshot documents the observed run, but grades should be based mainly on the student's quantitative analysis and the consistency of conclusions with the CSV.

## Expected qualitative behavior

| Profile | Expected behavior |
|---|---|
| Normal | Stage throughput remains similar; low or temporary backlog; moderate utilization; queue drains. |
| Burst | Short-lived backlog and latency increase; recovery after input drops. |
| Sustained | High utilization and persistent backlog when arrival rate approaches capacity. |
| Attack surge | Rapid backlog growth, increased queue waiting and E2E latency, possible overloaded status. |

Exact values depend on hardware and background load. Grade interpretation rather than matching fixed numbers.

## Suggested grading

| Component | Weight |
|---|---:|
| Correct CSV from assigned run | 20% |
| Accurate summary statistics | 20% |
| Charts and presentation | 15% |
| Bottleneck and queue analysis | 25% |
| Engineering recommendation | 10% |
| Reflection and reproducibility | 10% |

## Validation checks

- Filename follows the required convention.
- Profile and run ID are consistent across CSV, screenshot, and report.
- Generated, detected, and orchestrated counts are interpreted correctly.
- Conclusions refer to measured values.
- Internal JSONL files are not accepted as substitutes for the CSV.
