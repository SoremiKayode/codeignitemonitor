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
    activity: ActivitySnapshot | None = None


@dataclass(frozen=True, slots=True)
class ConnectionSnapshot:
    """One operating-system connection observation, not byte attribution."""

    pid: int | None
    process_name: str | None
    protocol: str
    local_address: str | None
    local_port: int | None
    remote_address: str | None
    remote_port: int | None
    state: str | None


@dataclass(frozen=True, slots=True)
class CarrierInfo:
    """Best-effort mobile broadband identity reported by the operating system."""

    provider_name: str | None
    interface_name: str | None
    source: str


@dataclass(frozen=True, slots=True)
class ActivitySnapshot:
    """Connection inventory suitable for display; it contains no traffic byte claims."""

    applications: tuple[tuple[str, int], ...] = ()
    connections: tuple[ConnectionSnapshot, ...] = ()
    carrier: CarrierInfo = CarrierInfo(None, None, "not detected")
    websites: tuple[WebsiteUsage, ...] = ()

@dataclass(frozen=True, slots=True)
class WebsiteUsage:
    """Bytes carried by one explicit local-proxy tunnel, grouped by hostname."""

    domain: str
    bytes_received: int
    bytes_sent: int
