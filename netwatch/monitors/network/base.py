from __future__ import annotations

from abc import ABC, abstractmethod

from netwatch.core.models import InterfaceSnapshot


class NetworkMonitor(ABC):
    """Counter source. Interface totals are explicitly not process attribution."""

    @abstractmethod
    def interfaces(self) -> list[InterfaceSnapshot]:
        raise NotImplementedError
