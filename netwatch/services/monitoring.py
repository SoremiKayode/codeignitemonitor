"""Background coordinator. It collects basic interface traffic without elevation."""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime

from netwatch.core.database import Database
from netwatch.core.models import DashboardSnapshot
from netwatch.monitors.network.base import NetworkMonitor
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
                day = now.date().isoformat()
                month = now.strftime("%Y-%m")
                today = self.database.usage_for_prefix(day)
                month_usage = self.database.usage_for_prefix(month)
                with self._lock:
                    self._snapshot = DashboardSnapshot(now, received / self.interval, sent / self.interval, *today, *month_usage)
            except Exception:
                self._log.exception("Network monitoring iteration failed; monitoring will continue")
        self.database.record_deltas(self.aggregator.drain())
