"""Local configuration with conservative, privacy-first defaults."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


def application_data_dir() -> Path:
    """Return a writable per-user directory without requiring elevation."""
    import os

    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return root / "NetWatchAnalyzer"


@dataclass(slots=True)
class Settings:
    monitoring_interval_seconds: float = 1.0
    flush_interval_seconds: float = 5.0
    selected_interfaces: list[str] = field(default_factory=list)
    monitor_domains: bool = True
    monitor_exact_urls: bool = False
    store_dns_events: bool = False
    store_connection_history: bool = False
    raw_retention_days: int = 7
    theme: str = "system"


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or application_data_dir() / "config" / "settings.json"

    def load(self) -> Settings:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = {key: value for key, value in raw.items() if key in Settings.__dataclass_fields__}
            return Settings(**allowed)
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
            return Settings()

    def save(self, settings: Settings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(settings), indent=2, sort_keys=True), encoding="utf-8")
