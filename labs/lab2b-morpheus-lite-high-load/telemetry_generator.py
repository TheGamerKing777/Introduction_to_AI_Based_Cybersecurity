from __future__ import annotations

import argparse
import random
import time
from datetime import datetime, timezone
import uuid

from morpheus_lite.config import load_settings
from morpheus_lite.high_load import LoadMetricsStore, RateController, RollingRate, epoch_ms, load_profiles
from morpheus_lite.kafka_io import create_producer, publish

USERS = ["alice", "bob", "charlie", "david", "admin", "svc-backup"]
HOSTS = ["host-01", "host-02", "host-03", "db-01", "web-01", "vpn-gw"]
IPS = ["10.0.0.10", "10.0.0.20", "10.0.0.30", "172.16.1.5", "192.168.1.8"]


def make_event(attack_probability: float = 0.12, *, sequence: int | None = None, profile: str = "baseline", run_id: str | None = None) -> dict:
    is_attack = random.random() < attack_probability
    return {
        "event_id": str(uuid.uuid4()),
        "correlation_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "generated_epoch_ms": epoch_ms(),
        "sequence": sequence,
        "load_profile": profile,
        "load_run_id": run_id,
        "user": random.choice(["admin", "svc-backup"] if is_attack else USERS),
        "host": random.choice(HOSTS),
        "src_ip": random.choice(["185.220.101.5", "45.155.205.12", "91.240.118.9"] if is_attack else IPS),
        "event_type": random.choice(["failed_login", "privilege_escalation", "suspicious_process"] if is_attack else ["login", "file_access", "dns_query", "http_request"]),
        "failed_logins": random.randint(8, 30) if is_attack else random.randint(0, 3),
        "bytes_out": random.randint(8_000_000, 50_000_000) if is_attack else random.randint(1_000, 500_000),
        "process_count": random.randint(150, 400) if is_attack else random.randint(20, 120),
        "country": random.choice(["RU", "CN", "IR", "KP"] if is_attack else ["IL", "US", "DE", "GB"]),
        "label": "suspicious" if is_attack else "normal",
        "schema_version": "1.1",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Morpheus Lite telemetry with selectable load profiles.")
    parser.add_argument("--profile", default="baseline", help="baseline, normal, burst, sustained, or attack_surge")
    parser.add_argument("--events", type=int, default=0, help="Stop after N events; 0 means run continuously")
    parser.add_argument("--rate", type=float, default=None, help="Override events per second")
    parser.add_argument("--attack-probability", type=float, default=None, help="Override attack probability (0-1)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    profiles = load_profiles(settings.raw)
    if args.profile not in profiles:
        raise SystemExit(f"Unknown profile '{args.profile}'. Available: {', '.join(sorted(profiles))}")
    profile = profiles[args.profile]
    if args.rate is not None:
        profile = type(profile)(profile.name, args.rate, profile.burst_size, profile.burst_interval_seconds, profile.attack_probability)
    if args.attack_probability is not None:
        profile = type(profile)(profile.name, profile.events_per_second, profile.burst_size, profile.burst_interval_seconds, args.attack_probability)

    producer = create_producer(settings)
    topic = settings.topic("raw_events")
    metrics = LoadMetricsStore(settings.raw.get("high_load", {}).get("metrics_jsonl", "data/high_load_metrics.jsonl"))
    controller = RateController(profile)
    run_id = str(uuid.uuid4())
    rate = RollingRate(float(settings.raw.get("high_load", {}).get("throughput_window_seconds", 5.0)))
    sent = 0
    metrics.record("generator", "run_started", 1, profile=profile.name, run_id=run_id, target_rate=profile.events_per_second)
    print(f"Producing telemetry to {topic} with profile={profile.name}, run_id={run_id}, target_rate={profile.events_per_second}/s")
    try:
        while args.events <= 0 or sent < args.events:
            sent += 1
            event = make_event(profile.attack_probability, sequence=sent, profile=profile.name, run_id=run_id)
            publish(producer, topic, event)
            recent_rate = rate.mark()
            metrics.record("generator", "events_sent", sent, profile=profile.name, run_id=run_id)
            metrics.record("generator", "throughput_eps", recent_rate, profile=profile.name, run_id=run_id)
            if sent <= 10 or sent % 100 == 0:
                print(f"sent={sent} type={event['event_type']} label={event['label']} recent_rate={recent_rate:.1f}/s")
            controller.wait_after_event(sent)
    finally:
        metrics.record("generator", "run_complete", sent, profile=profile.name, run_id=run_id)
        producer.close()


if __name__ == "__main__":
    main()
