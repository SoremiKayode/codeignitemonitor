from datetime import UTC, datetime

from netwatch.core.database import Database
from netwatch.core.models import TrafficDelta


def test_database_initializes_wal_schema_and_aggregates_usage(tmp_path) -> None:
    database = Database(tmp_path / "netwatch.sqlite3")
    database.initialize()
    database.record_deltas([
        TrafficDelta(datetime(2026, 8, 30, 12, tzinfo=UTC), "Wi-Fi", 120, 20),
        TrafficDelta(datetime(2026, 8, 30, 13, tzinfo=UTC), "Wi-Fi", 30, 10),
    ])
    assert database.usage_for_prefix("2026-08-30") == (150, 30)
    assert database.usage_for_prefix("2026-08") == (150, 30)
    assert database.integrity_check() == "ok"
