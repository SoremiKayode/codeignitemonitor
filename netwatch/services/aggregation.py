"""Counter arithmetic and bounded in-memory persistence buffering."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime

from netwatch.core.models import InterfaceSnapshot, TrafficDelta, TrafficSample


def counter_delta(current: int, previous: int) -> int:
    """Calculate a safe delta, treating counter resets as a new counter baseline."""
    if current < 0 or previous < 0:
        raise ValueError("network counters cannot be negative")
    return current if current < previous else current - previous


class NetworkAggregator:
    def __init__(self, max_buffer_size: int = 10_000) -> None:
        self._previous: dict[str, TrafficSample] = {}
        self._pending: deque[TrafficDelta] = deque(maxlen=max_buffer_size)

    def observe(self, interfaces: list[InterfaceSnapshot], timestamp: datetime | None = None) -> list[TrafficDelta]:
        now = timestamp or datetime.now(UTC)
        deltas: list[TrafficDelta] = []
        for interface in interfaces:
            sample = TrafficSample(now, interface.name, interface.bytes_received, interface.bytes_sent)
            previous = self._previous.get(interface.name)
            self._previous[interface.name] = sample
            if previous is None:
                continue
            delta = TrafficDelta(now, interface.name, counter_delta(sample.bytes_received, previous.bytes_received), counter_delta(sample.bytes_sent, previous.bytes_sent))
            deltas.append(delta)
            self._pending.append(delta)
        return deltas

    def drain(self) -> list[TrafficDelta]:
        values = list(self._pending)
        self._pending.clear()
        return values
