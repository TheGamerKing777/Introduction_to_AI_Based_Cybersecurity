from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from typing import Any

from kafka import KafkaConsumer, KafkaProducer

from .config import Settings


def create_producer(settings: Settings) -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=settings.bootstrap_servers,
        value_serializer=lambda value: json.dumps(value, default=str).encode("utf-8"),
        retries=5,
        acks="all",
    )


def create_consumer(
    settings: Settings,
    topic_alias: str,
    group_id: str | None,
    *,
    auto_offset_reset: str | None = None,
    consumer_timeout_ms: int | None = None,
    client_id: str | None = None,
) -> KafkaConsumer:
    kwargs: dict[str, Any] = {
        "bootstrap_servers": settings.bootstrap_servers,
        "value_deserializer": lambda raw: json.loads(raw.decode("utf-8")),
        "auto_offset_reset": auto_offset_reset
        or settings.raw.get("kafka", {}).get("auto_offset_reset", "latest"),
        "enable_auto_commit": group_id is not None,
        "group_id": group_id,
    }
    if client_id is not None:
        kwargs["client_id"] = client_id
    if consumer_timeout_ms is not None:
        kwargs["consumer_timeout_ms"] = consumer_timeout_ms
    return KafkaConsumer(settings.topic(topic_alias), **kwargs)


def publish(producer: KafkaProducer, topic: str, value: dict[str, Any], *, flush: bool = True) -> None:
    """Publish a JSON value.

    ``flush=False`` is useful when one logical operation emits several related
    records; callers can enqueue them and flush once to avoid turning Kafka
    network round trips into an artificial high-load bottleneck.
    """
    producer.send(topic, value=value)
    if flush:
        producer.flush()


def iter_messages(consumer: KafkaConsumer) -> Iterator[dict[str, Any]]:
    for message in consumer:
        yield message.value


def ephemeral_group_id(prefix: str) -> str:
    """Return a unique consumer-group id for one laboratory process instance.

    A unique group prevents a stale or accidentally duplicated process from
    silently receiving all records intended for the current lab run.
    """
    clean = prefix.strip().replace(" ", "-") or "consumer"
    return f"{clean}-{uuid.uuid4().hex[:8]}"


def wait_for_assignment(consumer: KafkaConsumer, timeout_seconds: float = 10.0) -> set[Any]:
    """Poll until Kafka assigns at least one partition, or raise clearly.

    Establishing the assignment before the telemetry generator starts is
    important when ``auto_offset_reset='latest'``: it fixes the starting
    position before new records are produced instead of racing the generator.
    """
    deadline = time.monotonic() + max(0.1, float(timeout_seconds))
    while time.monotonic() < deadline:
        consumer.poll(timeout_ms=250)
        assigned = set(consumer.assignment())
        if assigned:
            return assigned
    raise RuntimeError(
        "Kafka consumer received no partition assignment. Confirm that "
        "Redpanda is healthy and that the subscribed topic exists."
    )
