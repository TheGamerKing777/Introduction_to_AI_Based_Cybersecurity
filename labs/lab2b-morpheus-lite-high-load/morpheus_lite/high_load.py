from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from collections import deque
import json
import time


@dataclass(frozen=True)
class LoadProfile:
    name: str
    events_per_second: float
    burst_size: int = 1
    burst_interval_seconds: float = 0.0
    attack_probability: float = 0.12


DEFAULT_PROFILES: dict[str, LoadProfile] = {
    "baseline": LoadProfile("baseline", events_per_second=1.0, attack_probability=0.12),
    "normal": LoadProfile("normal", events_per_second=25.0, attack_probability=0.12),
    "burst": LoadProfile("burst", events_per_second=100.0, burst_size=250, burst_interval_seconds=2.5, attack_probability=0.20),
    "sustained": LoadProfile("sustained", events_per_second=250.0, attack_probability=0.18),
    "attack_surge": LoadProfile("attack_surge", events_per_second=500.0, burst_size=500, burst_interval_seconds=1.0, attack_probability=0.65),
}


def load_profiles(raw_settings: dict[str, Any]) -> dict[str, LoadProfile]:
    profiles = dict(DEFAULT_PROFILES)
    configured = raw_settings.get("high_load", {}).get("profiles", {})
    for name, cfg in configured.items():
        profiles[name] = LoadProfile(
            name=name,
            events_per_second=float(cfg.get("events_per_second", 1.0)),
            burst_size=max(1, int(cfg.get("burst_size", 1))),
            burst_interval_seconds=max(0.0, float(cfg.get("burst_interval_seconds", 0.0))),
            attack_probability=min(1.0, max(0.0, float(cfg.get("attack_probability", 0.12)))),
        )
    return profiles


class RateController:
    def __init__(self, profile: LoadProfile):
        self.profile = profile
        self._next_tick = time.perf_counter()

    def wait_after_event(self, event_index: int) -> None:
        if self.profile.burst_size > 1:
            if event_index % self.profile.burst_size == 0:
                time.sleep(self.profile.burst_interval_seconds)
            return
        interval = 1.0 / max(self.profile.events_per_second, 0.001)
        self._next_tick += interval
        delay = self._next_tick - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        else:
            self._next_tick = time.perf_counter()


class RollingRate:
    """Compute a recent throughput rate over a bounded sliding window."""

    def __init__(self, window_seconds: float = 5.0):
        self.window_seconds = max(0.5, float(window_seconds))
        self._timestamps: deque[float] = deque()

    def mark(self, timestamp: float | None = None) -> float:
        now = time.perf_counter() if timestamp is None else float(timestamp)
        self._timestamps.append(now)
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        if len(self._timestamps) < 2:
            return float(len(self._timestamps)) / self.window_seconds
        observed = max(now - self._timestamps[0], 1e-6)
        return (len(self._timestamps) - 1) / observed


def epoch_ms() -> float:
    """Wall-clock milliseconds suitable for timestamps shared across processes."""
    return time.time_ns() / 1_000_000.0


class LoadMetricsStore:
    """Append-only JSONL metrics store for the educational high-load lab."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def record(self, component: str, metric: str, value: float, **labels: Any) -> None:
        item = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": component,
            "metric": metric,
            "value": float(value),
            "labels": labels,
        }
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, default=str) + "\n")

    def read(self, limit: int = 5000) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
        records: list[dict[str, Any]] = []
        for line in lines:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records


def processing_delay_seconds(raw_settings: dict[str, Any], component: str) -> float:
    cfg = raw_settings.get("high_load", {}).get("processing_delay_ms", {})
    return max(0.0, float(cfg.get(component, 0.0)) / 1000.0)


def system_status(detector_util: float, orchestrator_util: float, ingress_backlog: int, alert_backlog: int, *, warning_utilization: float = 70.0, critical_utilization: float = 90.0, warning_backlog_ratio: float = 0.50, critical_backlog_ratio: float = 0.85, ingress_capacity: int = 500, alert_capacity: int = 500) -> tuple[str, str]:
    """Return a simple educational system-health label and explanation."""
    ingress_ratio = ingress_backlog / max(1, ingress_capacity)
    alert_ratio = alert_backlog / max(1, alert_capacity)
    peak_util = max(detector_util, orchestrator_util)
    peak_backlog = max(ingress_ratio, alert_ratio)
    if peak_util >= critical_utilization or peak_backlog >= critical_backlog_ratio:
        return "OVERLOADED", "Processing demand exceeds safe capacity; backlog or utilization is in the critical zone."
    if peak_util >= warning_utilization or peak_backlog >= warning_backlog_ratio:
        return "HIGH LOAD", "The pipeline is operating near capacity and backlog is accumulating."
    return "NORMAL", "The pipeline is keeping pace with the current workload."
