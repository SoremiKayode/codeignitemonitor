from datetime import UTC, datetime

import pytest

from netwatch.core.models import InterfaceSnapshot
from netwatch.services.aggregation import NetworkAggregator, counter_delta


def test_counter_delta_handles_reset_without_negative_usage() -> None:
    assert counter_delta(400, 1000) == 400
    assert counter_delta(1200, 1000) == 200
    with pytest.raises(ValueError):
        counter_delta(-1, 0)


def test_aggregator_uses_first_sample_as_baseline() -> None:
    monitor = NetworkAggregator()
    t = datetime(2026, 1, 1, tzinfo=UTC)
    first = InterfaceSnapshot("Ethernet", True, (), None, 100, 50)
    second = InterfaceSnapshot("Ethernet", True, (), None, 160, 80)
    assert monitor.observe([first], t) == []
    deltas = monitor.observe([second], t)
    assert [(delta.received, delta.sent) for delta in deltas] == [(60, 30)]
    assert monitor.drain() == deltas
