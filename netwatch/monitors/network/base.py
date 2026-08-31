from __future__ import annotations

from abc import ABC, abstractmethod

from netwatch.core.models import ConnectionSnapshot, InterfaceSnapshot


class NetworkMonitor(ABC):
    """Counter source. Interface totals are explicitly not process attribution."""

    @abstractmethod
    def interfaces(self) -> list[InterfaceSnapshot]:
        raise NotImplementedError

    def connections(self) -> list[ConnectionSnapshot]:
        """Return active connection ownership where the OS permits it.

        This is an inventory, not per-process byte accounting.
        """
        return []
