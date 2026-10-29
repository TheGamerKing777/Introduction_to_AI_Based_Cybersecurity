import sys
import types

fake_kafka = types.ModuleType('kafka')
fake_kafka.KafkaConsumer = object
fake_kafka.KafkaProducer = object
sys.modules.setdefault('kafka', fake_kafka)

from morpheus_lite.kafka_io import publish


class DummyProducer:
    def __init__(self):
        self.sent = []
        self.flush_count = 0

    def send(self, topic, value):
        self.sent.append((topic, value))

    def flush(self):
        self.flush_count += 1


def test_publish_can_batch_without_immediate_flush():
    producer = DummyProducer()
    publish(producer, 'a', {'x': 1}, flush=False)
    publish(producer, 'b', {'x': 2}, flush=False)
    assert producer.flush_count == 0
    producer.flush()
    assert producer.flush_count == 1
    assert len(producer.sent) == 2

from morpheus_lite.kafka_io import ephemeral_group_id, wait_for_assignment


def test_ephemeral_group_ids_are_unique_and_prefixed():
    first = ephemeral_group_id('agent orchestrator')
    second = ephemeral_group_id('agent orchestrator')
    assert first.startswith('agent-orchestrator-')
    assert second.startswith('agent-orchestrator-')
    assert first != second


class AssigningConsumer:
    def __init__(self):
        self.polls = 0

    def poll(self, timeout_ms):
        self.polls += 1
        return {}

    def assignment(self):
        return {'topic-0'} if self.polls >= 2 else set()


def test_wait_for_assignment_polls_until_ready():
    consumer = AssigningConsumer()
    assigned = wait_for_assignment(consumer, timeout_seconds=1)
    assert assigned == {'topic-0'}
    assert consumer.polls == 2
