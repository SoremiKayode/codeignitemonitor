"""SQLite persistence owned by the monitoring core, never by Qt widgets."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from .config import application_data_dir
from .models import TrafficDelta


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS network_interfaces (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL, is_selected INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS network_samples (
    id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, interface_name TEXT NOT NULL,
    bytes_received INTEGER NOT NULL CHECK(bytes_received >= 0),
    bytes_sent INTEGER NOT NULL CHECK(bytes_sent >= 0),
    FOREIGN KEY(interface_name) REFERENCES network_interfaces(name)
);
CREATE INDEX IF NOT EXISTS idx_network_samples_timestamp ON network_samples(timestamp);
CREATE INDEX IF NOT EXISTS idx_network_samples_interface_time ON network_samples(interface_name, timestamp);
CREATE TABLE IF NOT EXISTS daily_usage (
    day TEXT NOT NULL, interface_name TEXT NOT NULL,
    bytes_received INTEGER NOT NULL DEFAULT 0, bytes_sent INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(day, interface_name)
);
CREATE TABLE IF NOT EXISTS hourly_usage (
    hour TEXT NOT NULL, interface_name TEXT NOT NULL,
    bytes_received INTEGER NOT NULL DEFAULT 0, bytes_sent INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(hour, interface_name)
);
CREATE TABLE IF NOT EXISTS website_usage (
    day TEXT NOT NULL, domain TEXT NOT NULL,
    bytes_received INTEGER NOT NULL DEFAULT 0, bytes_sent INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(day, domain)
);
CREATE INDEX IF NOT EXISTS idx_website_usage_day ON website_usage(day);
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY, executable_path TEXT UNIQUE, display_name TEXT NOT NULL,
    first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS application_sessions (
    id INTEGER PRIMARY KEY, application_id INTEGER NOT NULL, pid INTEGER NOT NULL,
    process_started TEXT, session_ended TEXT, user_name TEXT,
    FOREIGN KEY(application_id) REFERENCES applications(id)
);
CREATE INDEX IF NOT EXISTS idx_application_sessions_pid ON application_sessions(pid);
CREATE TABLE IF NOT EXISTS connections (
    id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, pid INTEGER, protocol TEXT NOT NULL,
    local_address TEXT, local_port INTEGER, remote_address TEXT, remote_port INTEGER,
    state TEXT, attribution_level TEXT NOT NULL DEFAULT 'connection'
);
CREATE INDEX IF NOT EXISTS idx_connections_timestamp ON connections(timestamp);
CREATE TABLE IF NOT EXISTS domains (
    id INTEGER PRIMARY KEY, domain TEXT NOT NULL UNIQUE, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dns_events (
    id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, pid INTEGER, domain TEXT NOT NULL,
    resolved_ip TEXT, record_type TEXT, confidence TEXT NOT NULL DEFAULT 'observed'
);
CREATE TABLE IF NOT EXISTS browser_visits (
    id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, browser TEXT NOT NULL, tab_id INTEGER,
    url TEXT NOT NULL, domain TEXT NOT NULL, title TEXT
);
CREATE TABLE IF NOT EXISTS storage_scans (
    id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, completed_at TEXT, root_path TEXT NOT NULL,
    file_count INTEGER NOT NULL DEFAULT 0, inaccessible_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS storage_items (
    id INTEGER PRIMARY KEY, scan_id INTEGER NOT NULL, path TEXT NOT NULL, size_bytes INTEGER NOT NULL,
    is_directory INTEGER NOT NULL, extension TEXT, FOREIGN KEY(scan_id) REFERENCES storage_scans(id)
);
CREATE INDEX IF NOT EXISTS idx_storage_items_path ON storage_items(path);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0
);
"""


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or application_data_dir() / "data" / "netwatch.sqlite3"

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.executescript(SCHEMA)

    def record_deltas(self, deltas: list[TrafficDelta]) -> None:
        if not deltas:
            return
        with self.connect() as connection:
            for delta in deltas:
                timestamp = delta.timestamp.astimezone(UTC).isoformat()
                day = delta.timestamp.date().isoformat()
                hour = delta.timestamp.strftime("%Y-%m-%dT%H:00:00")
                connection.execute("INSERT INTO network_interfaces(name, first_seen, last_seen) VALUES(?, ?, ?) ON CONFLICT(name) DO UPDATE SET last_seen=excluded.last_seen", (delta.interface, timestamp, timestamp))
                connection.execute("INSERT INTO network_samples(timestamp, interface_name, bytes_received, bytes_sent) VALUES (?, ?, ?, ?)", (timestamp, delta.interface, delta.received, delta.sent))
                for table, bucket in (("daily_usage", day), ("hourly_usage", hour)):
                    connection.execute(f"INSERT INTO {table}(day, interface_name, bytes_received, bytes_sent) VALUES (?, ?, ?, ?) ON CONFLICT(day, interface_name) DO UPDATE SET bytes_received=bytes_received + excluded.bytes_received, bytes_sent=bytes_sent + excluded.bytes_sent" if table == "daily_usage" else f"INSERT INTO {table}(hour, interface_name, bytes_received, bytes_sent) VALUES (?, ?, ?, ?) ON CONFLICT(hour, interface_name) DO UPDATE SET bytes_received=bytes_received + excluded.bytes_received, bytes_sent=bytes_sent + excluded.bytes_sent", (bucket, delta.interface, delta.received, delta.sent))

    def usage_for_prefix(self, prefix: str) -> tuple[int, int]:
        with self.connect() as connection:
            row = connection.execute("SELECT COALESCE(SUM(bytes_received), 0), COALESCE(SUM(bytes_sent), 0) FROM daily_usage WHERE day LIKE ?", (f"{prefix}%",)).fetchone()
        return int(row[0]), int(row[1])

    def record_website_usage(self, timestamp: datetime, domain: str, received: int, sent: int) -> None:
        """Persist bytes observed by the explicit local proxy for a hostname."""
        if not domain or received < 0 or sent < 0:
            raise ValueError("website usage requires a domain and non-negative byte counts")
        with self.connect() as connection:
            connection.execute("INSERT INTO website_usage(day, domain, bytes_received, bytes_sent) VALUES (?, ?, ?, ?) ON CONFLICT(day, domain) DO UPDATE SET bytes_received=bytes_received + excluded.bytes_received, bytes_sent=bytes_sent + excluded.bytes_sent", (timestamp.date().isoformat(), domain.lower(), received, sent))

    def website_usage_for_day(self, day: str, limit: int = 100) -> list[tuple[str, int, int]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT domain, bytes_received, bytes_sent FROM website_usage WHERE day = ? ORDER BY bytes_received + bytes_sent DESC, domain LIMIT ?", (day, limit)).fetchall()
        return [(str(row[0]), int(row[1]), int(row[2])) for row in rows]

    def integrity_check(self) -> str:
        with self.connect() as connection:
            return str(connection.execute("PRAGMA integrity_check").fetchone()[0])
