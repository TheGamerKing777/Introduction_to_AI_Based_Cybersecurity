from morpheus_lite.high_load import LoadMetricsStore, load_profiles


def test_default_profiles_are_available():
    profiles = load_profiles({})
    assert profiles["baseline"].events_per_second == 1.0
    assert profiles["attack_surge"].attack_probability > profiles["baseline"].attack_probability


def test_configured_profile_overrides_default():
    profiles = load_profiles({"high_load": {"profiles": {"burst": {"events_per_second": 123, "burst_size": 20, "attack_probability": 0.4}}}})
    assert profiles["burst"].events_per_second == 123
    assert profiles["burst"].burst_size == 20
    assert profiles["burst"].attack_probability == 0.4


def test_metrics_store_round_trip(tmp_path):
    store = LoadMetricsStore(tmp_path / "metrics.jsonl")
    store.record("generator", "throughput_eps", 42.5, profile="burst")
    records = store.read()
    assert records[0]["component"] == "generator"
    assert records[0]["value"] == 42.5
    assert records[0]["labels"]["profile"] == "burst"

from morpheus_lite.high_load import RollingRate, epoch_ms


def test_rolling_rate_uses_recent_window():
    rate = RollingRate(window_seconds=5.0)
    assert rate.mark(10.0) == 0.2
    measured = rate.mark(11.0)
    assert 0.9 <= measured <= 1.1
    measured = rate.mark(12.0)
    assert 0.9 <= measured <= 1.1


def test_epoch_ms_is_wall_clock():
    import time
    assert abs(epoch_ms() - time.time() * 1000) < 1000

from morpheus_lite.high_load import system_status


def test_system_status_classifies_normal_high_and_overloaded():
    assert system_status(20, 10, 5, 5)[0] == "NORMAL"
    assert system_status(75, 10, 5, 5)[0] == "HIGH LOAD"
    assert system_status(95, 10, 5, 5)[0] == "OVERLOADED"
    assert system_status(20, 10, 450, 5, ingress_capacity=500)[0] == "OVERLOADED"
