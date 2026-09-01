from datetime import UTC, date, datetime

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
    assert database.usage_between(date(2026, 8, 29), date(2026, 8, 31)) == [("2026-08-30", 150, 30)]


def test_database_aggregates_proxy_website_usage(tmp_path) -> None:
    database = Database(tmp_path / "netwatch.sqlite3")
    database.initialize()
    timestamp = datetime(2026, 8, 30, 12, tzinfo=UTC)
    database.record_website_usage(timestamp, "Example.COM", 120, 20)
    database.record_website_usage(timestamp, "example.com", 30, 10)
    assert database.website_usage_for_day("2026-08-30") == [("example.com", 150, 30)]
    database.record_website_usage(datetime(2026, 8, 31, 12, tzinfo=UTC), "other.test", 50, 5)
    assert database.website_usage_between(date(2026, 8, 30), date(2026, 8, 31)) == [
        ("example.com", 150, 30),
        ("other.test", 50, 5),
    ]


def test_database_rejects_inverted_ranges(tmp_path) -> None:
    database = Database(tmp_path / "netwatch.sqlite3")
    database.initialize()
    import pytest

    with pytest.raises(ValueError, match="end date"):
        database.usage_between(date(2026, 9, 1), date(2026, 8, 1))
