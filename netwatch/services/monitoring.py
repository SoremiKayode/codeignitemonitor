"""Background coordinator. It collects basic interface traffic without elevation."""

from __future__ import annotations

import logging
import threading
from datetime import UTC, date, datetime

from netwatch.core.database import Database
from netwatch.core.models import ActivitySnapshot, DashboardSnapshot, WebsiteUsage
from netwatch.monitors.network.base import NetworkMonitor
from netwatch.monitors.network.carrier import WindowsCarrierDetector
from netwatch.services.aggregation import NetworkAggregator


class MonitoringService:
    def __init__(self, provider: NetworkMonitor, database: Database, interval: float = 1.0, flush_interval: float = 5.0) -> None:
        self.provider, self.database = provider, database
        self.interval, self.flush_interval = interval, flush_interval
        self.aggregator = NetworkAggregator()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._snapshot = DashboardSnapshot(datetime.now(UTC), 0, 0, 0, 0, 0, 0)
        self._lock = threading.Lock()
        self._log = logging.getLogger(__name__)
        self._carrier_detector = WindowsCarrierDetector()
        self._activity = ActivitySnapshot()
        self._last_activity_refresh: datetime | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.database.initialize()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="netwatch-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self.interval * 3)

    def snapshot(self) -> DashboardSnapshot:
        with self._lock:
            return self._snapshot

    def usage_between(self, start: date, end: date) -> list[tuple[str, int, int]]:
        return self.database.usage_between(start, end)

    def website_usage_between(self, start: date, end: date) -> list[tuple[str, int, int]]:
        return self.database.website_usage_between(start, end)

    def _run(self) -> None:
        last_flush = datetime.now(UTC)
        while not self._stop.wait(self.interval):
            try:
                now = datetime.now(UTC)
                deltas = self.aggregator.observe(self.provider.interfaces(), now)
                received, sent = sum(d.received for d in deltas), sum(d.sent for d in deltas)
                if (now - last_flush).total_seconds() >= self.flush_interval:
                    self.database.record_deltas(self.aggregator.drain())
                    last_flush = now
                if self._last_activity_refresh is None or (now - self._last_activity_refresh).total_seconds() >= 5:
                    connections = tuple(self.provider.connections())
                    counts: dict[str, int] = {}
                    for connection in connections:
                        name = connection.process_name or (f"PID {connection.pid}" if connection.pid else "System / unknown")
                        counts[name] = counts.get(name, 0) + 1
                    websites = tuple(WebsiteUsage(domain, received, sent) for domain, received, sent in self.database.website_usage_for_day(now.date().isoformat()))
                    self._activity = ActivitySnapshot(tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0]))), connections, self._carrier_detector.detect(), websites)
                    self._last_activity_refresh = now
                day = now.date().isoformat()
                month = now.strftime("%Y-%m")
                today = self.database.usage_for_prefix(day)
                month_usage = self.database.usage_for_prefix(month)
                with self._lock:
                    self._snapshot = DashboardSnapshot(now, received / self.interval, sent / self.interval, *today, *month_usage, self._activity)
            except Exception:
                self._log.exception("Network monitoring iteration failed; monitoring will continue")
        self.database.record_deltas(self.aggregator.drain())
