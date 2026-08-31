from __future__ import annotations

from netwatch.core.models import InterfaceSnapshot
from netwatch.monitors.network.base import NetworkMonitor


class MockNetworkMonitor(NetworkMonitor):
    """Deterministic provider for UI development and automated tests."""
    def __init__(self, received: int = 0, sent: int = 0) -> None:
        self.received, self.sent = received, sent

    def advance(self, received: int, sent: int) -> None:
        self.received += received
        self.sent += sent

    def interfaces(self) -> list[InterfaceSnapshot]:
        return [InterfaceSnapshot("Mock Ethernet", True, ("192.0.2.10",), "00:00:5E:00:53:01", self.received, self.sent)]
