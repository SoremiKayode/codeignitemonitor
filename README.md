# NetWatch Analyzer

NetWatch Analyzer is a **visible, local-first Windows desktop foundation** for monitoring network interfaces and analyzing storage. It is intentionally designed to distinguish reliable measurements from data that Windows does not expose at normal user privilege.

## Current working capabilities

- A PySide6 dark dashboard shell driven by a background monitoring service.
- Real interface-level receive/send counters through `psutil`, sampled in memory and flushed to SQLite in batches.
- SQLite WAL database with raw samples and hourly/daily rollups, integrity checks, and indexed time queries.
- Safe storage scan: iterative traversal, cancellation, permission-error collection, default exclusions, and no symbolic-link recursion.
- Staged duplicate detection: equal-size candidates, partial SHA-256, then full SHA-256.
- Deterministic mock network provider and unit tests for counter resets, persistence, scanning, and duplicate detection.

## Accuracy and privacy

Interface traffic is currently the only traffic shown as measured. It is **not assigned to processes**. Process-level byte counts, domain traffic attribution, DNS events, and browser URL history are not implemented by this initial foundation and must remain unavailable until an audited Windows ETW/WFP provider and explicit attribution confidence model are added.

All data stays in the current user's local application-data directory by default. The application has no remote API, no stealth persistence, and does not collect passwords, cookies, keystrokes, page content, or authentication tokens. HTTPS encrypts URL paths; domain activity and exact browser navigation are separate capabilities.

## Architecture

```
PySide6 dashboard -> MonitoringService -> NetworkMonitor provider -> SQLite (WAL)
                                          -> bounded NetworkAggregator
StorageScanner / duplicate detector -----------------------------> UI or repository
```

The UI only reads service snapshots; it does not access SQLite or operating-system counters directly. `NetworkMonitor` is an interface, allowing a future Windows-native advanced provider and the included mock provider to be swapped in without changing the UI.

## Development setup

Requires Python 3.12+ (the project is tested with current CPython) and Windows 10/11 for the desktop target.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
netwatch
```

To verify database initialization and service startup without PySide6:

```powershell
python -m netwatch.app --headless-check
```

## Permissions and platform notes

Basic interface monitoring and user-folder scans work as a standard user. Some directories will be reported as inaccessible instead of stopping a scan. Administrator elevation is not requested by this version. A future provider may offer opt-in elevated ETW/WFP collection, clearly labeled by source and confidence.

## Roadmap

The next production phases are Windows connection enumeration via IP Helper API, an explicitly privileged per-process attribution provider, domain resolution cache/DNS observation, browser extensions with opt-in local-only URL navigation, historical UI/charting, exports/alerts, tray/background startup, and Windows packaging (PyInstaller/Inno Setup). No UI will claim these features are measured until their provider is implemented and tested.
