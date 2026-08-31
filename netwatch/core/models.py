"""Typed values exchanged between monitors, storage, and presentation layers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class TrafficSample:
    """A monotonic interface counter observation."""

    timestamp: datetime
    interface: str
    bytes_received: int
    bytes_sent: int


@dataclass(frozen=True, slots=True)
class TrafficDelta:
    """Traffic accrued between two samples, never containing negative values."""

    timestamp: datetime
    interface: str
    received: int
    sent: int


@dataclass(frozen=True, slots=True)
class InterfaceSnapshot:
    name: str
    is_up: bool
    addresses: tuple[str, ...]
    mac_address: str | None
    bytes_received: int
    bytes_sent: int


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    timestamp: datetime
    download_bytes_per_second: float
    upload_bytes_per_second: float
    today_download: int
    today_upload: int
    month_download: int
    month_upload: int
