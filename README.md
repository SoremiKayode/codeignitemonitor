# NetWatch Analyzer

NetWatch Analyzer is a **visible, local-first Windows desktop foundation** for monitoring network interfaces and analyzing storage. It is intentionally designed to distinguish reliable measurements from data that Windows does not expose at normal user privilege.

## Current working capabilities

- A PySide6 dark dashboard shell driven by a background monitoring service.
- Circular received/sent usage analytics for the last 24 hours, week, month, or an inclusive custom date range.
- Striped application, website, connection, history, large-file, and duplicate tables with explicit measurement-quality labels.
- Real interface-level receive/send counters through `psutil`, sampled in memory and flushed to SQLite in batches.
- Live active-connection inventory, including the operating-system-reported owning process where permission allows; this is clearly separated from byte attribution.
- An opt-in localhost web proxy that records per-hostname inbound/outbound tunnel bytes for browsers explicitly configured to use `127.0.0.1:8787`, with a live Websites table backed by SQLite.
- Best-effort mobile-carrier identification for Windows Mobile Broadband connections (for example MTN, Airtel, or Glo) through `netsh mbn`; it reports unavailable rather than guessing.
- Local folder scan UI that summarizes file count, file types, largest files, inaccessible paths, and duplicate candidate groups without changing or deleting files.
- Working large-file and duplicate review screens, 30-day CSV reports, monthly usage thresholds, and persisted monitoring preferences.
- SQLite WAL database with raw samples and hourly/daily rollups, integrity checks, and indexed time queries.
- Safe storage scan: iterative traversal, cancellation, permission-error collection, default exclusions, and no symbolic-link recursion.
- Staged duplicate detection: equal-size candidates, partial SHA-256, then full SHA-256.
- Deterministic mock network provider and unit tests for counter resets, persistence, scanning, and duplicate detection.

## Accuracy and privacy

Interface counters and bytes flowing through the opt-in local web proxy are the only traffic shown as measured bytes. Active connections can be associated with a process when the operating system permits it, but those connections are **not byte attribution**. Process-level byte counts, domain traffic attribution, DNS events, and browser URL history are not implemented and must remain unavailable until an audited Windows ETW/WFP provider and explicit attribution confidence model are added. A carrier name is shown only when Windows Mobile Broadband supplies it; Wi-Fi names, IP ranges, and remote endpoints are never used to infer a carrier.

All data stays in the current user's local application-data directory by default. The application has no remote API, no stealth persistence, and does not collect passwords, cookies, keystrokes, page content, or authentication tokens. HTTPS encrypts URL paths; domain activity and exact browser navigation are separate capabilities.

## Architecture

```
PySide6 dashboard -> MonitoringService -> NetworkMonitor provider -> SQLite (WAL)
                                          -> bounded NetworkAggregator
StorageScanner / duplicate detector -----------------------------> UI or repository
Psutil connection inventory + Windows carrier detector ---------> MonitoringService -> UI
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
