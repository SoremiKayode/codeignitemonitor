"""NetWatch desktop entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler

from netwatch.core.config import SettingsStore, application_data_dir
from netwatch.core.database import Database
from netwatch.monitors.network.system import PsutilNetworkMonitor
from netwatch.services.monitoring import MonitoringService
from netwatch.services.local_proxy import LocalUsageProxy


def configure_logging() -> None:
    directory = application_data_dir() / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / "application.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NetWatch Analyzer desktop monitor")
    parser.add_argument("--headless-check", action="store_true", help="initialize local services without Qt")
    args = parser.parse_args(argv)
    configure_logging()
    settings = SettingsStore().load()
    service = MonitoringService(PsutilNetworkMonitor(), Database(), settings.monitoring_interval_seconds, settings.flush_interval_seconds)
    service.start()
    proxy = LocalUsageProxy(service.database)
    proxy.start()
    if args.headless_check:
        proxy.stop()
        service.stop()
        return 0
    try:
        from netwatch.ui.main_window import create_main_window
        app, window = create_main_window(service.snapshot)
        window.show()
        return app.exec()
    except ImportError:
        logging.getLogger(__name__).exception("PySide6 is unavailable")
        print("PySide6 is required for the desktop UI. Install project dependencies first.", file=sys.stderr)
        return 2
    finally:
        proxy.stop()
        service.stop()


if __name__ == "__main__":
    raise SystemExit(main())
