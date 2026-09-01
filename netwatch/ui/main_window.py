"""Modern, transparent desktop dashboard driven by the monitoring service.

The UI deliberately distinguishes live interface measurements from features that
need an opt-in advanced Windows provider.  Every navigation item therefore has
an informative screen instead of a blank placeholder or inferred data.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from collections.abc import Callable

from netwatch.core.models import DashboardSnapshot
from netwatch.monitors.storage.duplicate import find_duplicates
from netwatch.monitors.storage.scanner import StorageScanner


NAVIGATION = (
    ("Dashboard", "Overview"),
    ("Network usage", "Network"),
    ("Applications", "Applications"),
    ("Websites", "Websites"),
    ("Connections", "Connections"),
    ("History", "History"),
    ("Storage", "Storage"),
    ("Large files", "LargeFiles"),
    ("Duplicates", "Duplicates"),
    ("Reports", "Reports"),
    ("Alerts", "Alerts"),
    ("Settings", "Settings"),
    ("About", "About"),
)

PAGE_DETAILS = {
    "Websites": ("Website activity", "Website byte attribution is not available.", "NetWatch never guesses website usage from connections. Exact website activity needs an explicit, opt-in browser or DNS integration; HTTPS page paths and page content are never collected."),
    "History": ("Usage history", "Historical charts arrive as data is recorded.", "Network totals are stored locally in SQLite. This screen will expand to date ranges and exports as the history query layer is added."),
    "Storage": ("Storage analysis", "Scan a folder to understand disk usage.", "Storage scans are safe and local: inaccessible folders are recorded rather than stopping a scan, and symbolic links are not followed."),
    "LargeFiles": ("Large files", "Find files worth reviewing.", "Choose a storage scan from the Storage section first. Results will be grouped by size, type, and location without deleting anything automatically."),
    "Duplicates": ("Duplicate files", "Review space-saving opportunities safely.", "Duplicate detection uses a staged size and SHA-256 comparison. Nothing is removed unless you explicitly choose to do so."),
    "Reports": ("Reports", "Create a clear local usage summary.", "Reports will combine recorded network totals and completed storage scans. Export controls are intentionally unavailable until the report contents are complete."),
    "Alerts": ("Alerts", "You are all caught up.", "Alerts will be shown here only for rules you enable, such as a bandwidth threshold or completed storage scan."),
    "Settings": ("Settings", "Monitoring runs locally in the background.", "Sampling and retention settings are saved in your local application-data folder. Advanced collection will always be opt-in and clearly explained."),
    "About": ("About NetWatch", "A private, local-first monitor.", "NetWatch measures network interface counters with standard user permissions. It does not collect passwords, cookies, keystrokes, page content, or authentication tokens."),
}


def format_bytes(value: float, rate: bool = False) -> str:
    """Format a byte count for compact dashboard display."""
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    suffix = "/s" if rate else ""
    return f"{value:.1f} {units[index]}{suffix}"


def create_main_window(snapshot_provider: Callable[[], DashboardSnapshot]):
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import (
        QApplication, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
        QMainWindow, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    )

    class TrafficChart(QWidget):
        """A lightweight rolling traffic chart without a third-party chart dependency."""
        def __init__(self) -> None:
            super().__init__()
            self.setMinimumHeight(240)
            self._down: deque[float] = deque(maxlen=60)
            self._up: deque[float] = deque(maxlen=60)

        def append(self, down: float, up: float) -> None:
            self._down.append(down)
            self._up.append(up)
            self.update()

        def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = self.rect().adjusted(18, 18, -18, -30)
            painter.setPen(QPen(QColor("#273552"), 1))
            for step in range(5):
                y = rect.top() + rect.height() * step / 4
                painter.drawLine(rect.left(), int(y), rect.right(), int(y))
            if not self._down:
                painter.setPen(QColor("#7f91ad"))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Collecting live traffic…")
                return
            maximum = max(max(self._down), max(self._up), 1.0)
            for values, color in ((self._down, QColor("#59a6ff")), (self._up, QColor("#31d0aa"))):
                path = QPainterPath()
                count = len(values)
                for index, value in enumerate(values):
                    x = rect.left() + (rect.width() * index / max(count - 1, 1))
                    y = rect.bottom() - (rect.height() * value / maximum)
                    (path.moveTo if index == 0 else path.lineTo)(x, y)
                painter.setPen(QPen(color, 2.5))
                painter.drawPath(path)
            painter.setPen(QColor("#7f91ad"))
            painter.drawText(rect.left(), self.height() - 9, "Last 60 seconds")
            painter.drawText(rect.right() - 95, self.height() - 9, f"Peak {format_bytes(maximum, True)}")

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("NetWatch Analyzer")
            self.resize(1280, 800)
            root = QWidget()
            layout = QHBoxLayout(root)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            sidebar = QFrame()
            sidebar.setObjectName("sidebar")
            side_layout = QVBoxLayout(sidebar)
            side_layout.setContentsMargins(18, 22, 18, 18)
            brand = QLabel("NETWATCH\n<span>ANALYZER</span>")
            brand.setObjectName("brand")
            side_layout.addWidget(brand)
            side_layout.addSpacing(20)
            self.navigation = QListWidget()
            self.navigation.setObjectName("navigation")
            for title, key in NAVIGATION:
                item = QListWidgetItem(title)
                item.setData(Qt.ItemDataRole.UserRole, key)
                self.navigation.addItem(item)
            side_layout.addWidget(self.navigation, 1)
            status = QLabel("●  MONITORING ACTIVE\nInterface counters · local only")
            status.setObjectName("status")
            side_layout.addWidget(status)
            layout.addWidget(sidebar)
            self.pages = QStackedWidget()
            self.pages.setObjectName("pages")
            self.pages.addWidget(self._overview())
            self.pages.addWidget(self._network_page())
            self.pages.addWidget(self._applications_page())
            self.pages.addWidget(self._websites_page())
            self.pages.addWidget(self._connections_page())
            self.pages.addWidget(self._storage_page())
            for _, key in NAVIGATION[6:]:
                self.pages.addWidget(self._info_page(*PAGE_DETAILS[key]))
            layout.addWidget(self.pages, 1)
            self.setCentralWidget(root)
            self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
            self.navigation.setCurrentRow(0)
            timer = QTimer(self)
            timer.timeout.connect(self.refresh)
            timer.start(1000)
            self.refresh()

        def _page_shell(self, eyebrow: str, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
            page = QWidget()
            page.setObjectName("page")
            column = QVBoxLayout(page)
            column.setContentsMargins(38, 30, 38, 32)
            column.setSpacing(14)
            label = QLabel(eyebrow.upper())
            label.setObjectName("eyebrow")
            column.addWidget(label)
            heading = QLabel(title)
            heading.setObjectName("pageTitle")
            column.addWidget(heading)
            description = QLabel(subtitle)
            description.setObjectName("subtitle")
            description.setWordWrap(True)
            column.addWidget(description)
            return page, column

        def _overview(self) -> QWidget:
            page, column = self._page_shell("Live workspace", "Good morning, your network is in view.", "A live, local snapshot of all network interfaces. Figures update every second.")
            cards = QHBoxLayout()
            self.download = self._metric_card("DOWNLOAD", "Live receive rate", "↓", "blue")
            self.upload = self._metric_card("UPLOAD", "Live send rate", "↑", "green")
            self.today = self._metric_card("TODAY", "Recorded since midnight", "↕", "violet")
            for card in (self.download, self.upload, self.today):
                cards.addWidget(card)
            column.addLayout(cards)
            chart_card = QFrame(); chart_card.setObjectName("panel")
            chart_layout = QVBoxLayout(chart_card)
            chart_layout.addWidget(QLabel("TRAFFIC FLOW", objectName="panelTitle"))
            legend = QLabel("● Download   <span>● Upload</span>")
            legend.setObjectName("legend")
            chart_layout.addWidget(legend)
            self.chart = TrafficChart()
            chart_layout.addWidget(self.chart)
            column.addWidget(chart_card, 1)
            footer = QLabel("Measured: interface-level traffic  •  Not inferred: apps, websites, and per-process traffic")
            footer.setObjectName("footer")
            column.addWidget(footer)
            return page

        def _network_page(self) -> QWidget:
            page, column = self._page_shell("Network", "Usage at a glance", "All totals come from the active interface counters and are recorded locally.")
            panel = QFrame(); panel.setObjectName("panel")
            panel_layout = QVBoxLayout(panel)
            self.month_total = QLabel("--"); self.month_total.setObjectName("heroValue")
            panel_layout.addWidget(QLabel("THIS MONTH", objectName="panelTitle")); panel_layout.addWidget(self.month_total)
            self.month_detail = QLabel("Waiting for the first sample…"); self.month_detail.setObjectName("muted")
            panel_layout.addWidget(self.month_detail)
            column.addWidget(panel)
            disclosure = QFrame(); disclosure.setObjectName("disclosure")
            disclosure_layout = QVBoxLayout(disclosure)
            disclosure_layout.addWidget(QLabel("DATA QUALITY", objectName="panelTitle"))
            disclosure_layout.addWidget(QLabel("These figures measure traffic for network interfaces. They are accurate totals, but are not assigned to an application, person, website, or browser tab."))
            column.addWidget(disclosure)
            column.addStretch()
            return page

        def _applications_page(self) -> QWidget:
            page, column = self._page_shell("Connection ownership", "Applications with active connections", "This is a live connection inventory—not per-app data consumption. Byte attribution requires a dedicated Windows provider.")
            panel = QFrame(); panel.setObjectName("panel")
            layout = QVBoxLayout(panel); layout.addWidget(QLabel("ACTIVE APPLICATIONS", objectName="panelTitle"))
            self.application_list = QLabel("Waiting for connection inventory…"); self.application_list.setObjectName("inventory"); self.application_list.setWordWrap(True)
            layout.addWidget(self.application_list); column.addWidget(panel); column.addStretch()
            return page

        def _websites_page(self) -> QWidget:
            page, column = self._page_shell("Proxy website usage", "Website data consumption", "Website bytes are recorded only for browsers or apps configured to use NetWatch’s local proxy at 127.0.0.1:8787. HTTPS remains encrypted; NetWatch records the hostname and tunnel byte totals, not pages or content.")
            notice = QFrame(); notice.setObjectName("disclosure"); notice_layout = QVBoxLayout(notice)
            notice_layout.addWidget(QLabel("TO CAPTURE WEBSITE USAGE", objectName="panelTitle"))
            notice_layout.addWidget(QLabel("Set your browser’s HTTP and HTTPS proxy to 127.0.0.1, port 8787. Traffic that bypasses the proxy cannot be assigned to a website."))
            column.addWidget(notice)
            self.website_table = QTableWidget(0, 3); self.website_table.setHorizontalHeaderLabels(["Website", "Received", "Sent"]); self.website_table.setObjectName("usageTable")
            self.website_table.horizontalHeader().setStretchLastSection(True); self.website_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.website_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            column.addWidget(self.website_table, 1)
            return page

        def _connections_page(self) -> QWidget:
            page, column = self._page_shell("Live inventory", "Current network connections", "Remote addresses are shown as reported by the operating system. They are not treated as website visits or traffic totals.")
            carrier = QFrame(); carrier.setObjectName("disclosure"); layout = QVBoxLayout(carrier)
            layout.addWidget(QLabel("MOBILE NETWORK", objectName="panelTitle"))
            self.carrier_label = QLabel("Checking Windows mobile broadband…"); self.carrier_label.setObjectName("inventory"); layout.addWidget(self.carrier_label)
            column.addWidget(carrier)
            panel = QFrame(); panel.setObjectName("panel"); layout = QVBoxLayout(panel); layout.addWidget(QLabel("ACTIVE REMOTE ENDPOINTS", objectName="panelTitle"))
            self.connection_list = QLabel("Waiting for connection inventory…"); self.connection_list.setObjectName("inventory"); self.connection_list.setWordWrap(True); layout.addWidget(self.connection_list)
            column.addWidget(panel); column.addStretch()
            return page

        def _storage_page(self) -> QWidget:
            from PySide6.QtWidgets import QFileDialog, QPushButton
            page, column = self._page_shell("File information", "Storage scan and review", "Choose a folder to calculate its files, size, file types, and duplicate candidates. Scans are local and never delete files.")
            panel = QFrame(); panel.setObjectName("panel"); layout = QVBoxLayout(panel)
            button = QPushButton("Choose folder and scan"); button.setObjectName("scanButton"); layout.addWidget(button)
            self.storage_result = QLabel("No folder scanned yet."); self.storage_result.setObjectName("inventory"); self.storage_result.setWordWrap(True); layout.addWidget(self.storage_result)
            column.addWidget(panel); column.addStretch()
            def scan_folder() -> None:
                selected = QFileDialog.getExistingDirectory(self, "Choose a folder to scan")
                if not selected:
                    return
                self.storage_result.setText("Scanning files locally…")
                result = StorageScanner().scan(Path(selected))
                groups = find_duplicates(result.files)
                largest = sorted(result.files, key=lambda item: item.size_bytes, reverse=True)[:5]
                types = result.by_extension().most_common(5)
                largest_text = "\n".join(f"{format_bytes(item.size_bytes)} — {item.path.name}" for item in largest) or "No files found"
                types_text = ", ".join(f"{extension}: {format_bytes(size)}" for extension, size in types) or "No file types"
                self.storage_result.setText(f"{len(result.files):,} files · {format_bytes(result.total_bytes)} · {len(result.inaccessible)} inaccessible paths · {len(groups)} duplicate groups\nTop file types: {types_text}\nLargest files:\n{largest_text}")
            button.clicked.connect(scan_folder)
            return page

        def _info_page(self, title: str, state: str, detail: str) -> QWidget:
            page, column = self._page_shell("Workspace", title, state)
            panel = QFrame(); panel.setObjectName("emptyPanel")
            panel_layout = QVBoxLayout(panel)
            panel_layout.addWidget(QLabel("WHAT TO EXPECT", objectName="panelTitle"))
            detail_label = QLabel(detail); detail_label.setObjectName("emptyCopy"); detail_label.setWordWrap(True)
            panel_layout.addWidget(detail_label)
            badge = QLabel("LOCAL-FIRST · NO DATA IS BEING INFERRED")
            badge.setObjectName("badge")
            panel_layout.addWidget(badge)
            column.addWidget(panel)
            column.addStretch()
            return page

        def _metric_card(self, label: str, caption: str, symbol: str, accent: str) -> QFrame:
            frame = QFrame(); frame.setObjectName("metric"); frame.setProperty("accent", accent)
            card = QVBoxLayout(frame)
            top = QHBoxLayout()
            top.addWidget(QLabel(label, objectName="metricLabel")); top.addStretch()
            icon = QLabel(symbol); icon.setObjectName("metricIcon"); top.addWidget(icon)
            card.addLayout(top)
            amount = QLabel("--"); amount.setObjectName("metricValue"); card.addWidget(amount)
            card.addWidget(QLabel(caption, objectName="metricCaption"))
            frame.amount = amount  # type: ignore[attr-defined]
            return frame

        def refresh(self) -> None:
            snapshot = snapshot_provider()
            self.download.amount.setText(format_bytes(snapshot.download_bytes_per_second, True))  # type: ignore[attr-defined]
            self.upload.amount.setText(format_bytes(snapshot.upload_bytes_per_second, True))  # type: ignore[attr-defined]
            self.today.amount.setText(format_bytes(snapshot.today_download + snapshot.today_upload))  # type: ignore[attr-defined]
            self.month_total.setText(format_bytes(snapshot.month_download + snapshot.month_upload))
            self.month_detail.setText(f"↓ {format_bytes(snapshot.month_download)} received   ·   ↑ {format_bytes(snapshot.month_upload)} sent")
            self.chart.append(snapshot.download_bytes_per_second, snapshot.upload_bytes_per_second)
            activity = snapshot.activity
            if activity and hasattr(self, "application_list"):
                self.application_list.setText("\n".join(f"{name} — {count} active connection{'s' if count != 1 else ''}" for name, count in activity.applications[:12]) or "No active internet connections reported.")
                carrier = activity.carrier
                provider = carrier.provider_name or "No carrier name reported"
                interface = f" on {carrier.interface_name}" if carrier.interface_name else ""
                self.carrier_label.setText(f"{provider}{interface}\n{carrier.source}")
                self.website_table.setRowCount(len(activity.websites))
                for row, website in enumerate(activity.websites):
                    for column, value in enumerate((website.domain, format_bytes(website.bytes_received), format_bytes(website.bytes_sent))):
                        self.website_table.setItem(row, column, QTableWidgetItem(value))
                rows = []
                for item in activity.connections[:12]:
                    app = item.process_name or (f"PID {item.pid}" if item.pid else "System / unknown")
                    endpoint = f"{item.remote_address}:{item.remote_port}" if item.remote_address else "No remote endpoint"
                    rows.append(f"{app}  →  {endpoint}  ·  {item.protocol} {item.state or ''}".strip())
                self.connection_list.setText("\n".join(rows) or "No active remote connections reported.")

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLESHEET)
    return app, MainWindow()


STYLESHEET = """
QWidget { background: #0c1322; color: #edf3ff; font: 10pt 'Segoe UI'; }
#sidebar { background: #101a2d; min-width: 236px; max-width: 236px; }
#brand { font-size: 17pt; font-weight: 800; letter-spacing: 2px; color: #f7faff; } #brand span { color: #5aa8ff; font-size: 9pt; letter-spacing: 4px; }
#navigation { border: 0; background: transparent; outline: 0; } #navigation::item { color: #9fb0cc; padding: 10px 12px; margin: 2px 0; border-radius: 8px; } #navigation::item:hover { background: #18253d; color: #fff; } #navigation::item:selected { background: #1d4f91; color: #fff; font-weight: 700; }
#status { color: #7f91ad; font-size: 8pt; line-height: 1.5; padding: 12px; background: #0c1526; border-radius: 9px; } #pages, #page { background: #0c1322; }
#eyebrow { color: #5aa8ff; font-size: 8pt; font-weight: 700; letter-spacing: 1.6px; } #pageTitle { font-size: 24pt; font-weight: 750; } #subtitle { color: #91a2bd; font-size: 11pt; max-width: 730px; }
#metric { background: #141f34; border: 1px solid #22304b; border-radius: 12px; min-height: 132px; } #metric[accent="blue"] { border-top: 3px solid #59a6ff; } #metric[accent="green"] { border-top: 3px solid #31d0aa; } #metric[accent="violet"] { border-top: 3px solid #a889ff; }
#metricLabel, #panelTitle { color: #90a4c5; font-size: 8pt; font-weight: 700; letter-spacing: 1.1px; } #metricIcon { color: #8abfff; font-size: 16pt; font-weight: 700; } #metricValue, #heroValue { font-size: 22pt; font-weight: 750; } #metricCaption, #muted { color: #7f91ad; font-size: 9pt; }
#panel, #emptyPanel, #disclosure { background: #141f34; border: 1px solid #22304b; border-radius: 12px; padding: 16px; } #disclosure { background: #10213a; border-color: #1d4f91; color: #bad7fb; } #emptyPanel { min-height: 175px; } #emptyCopy { color: #b4c1d5; font-size: 11pt; line-height: 1.5; max-width: 650px; }
#usageTable { background: #141f34; border: 1px solid #22304b; border-radius: 8px; gridline-color: #22304b; } #usageTable::item { padding: 7px; } #usageTable QHeaderView::section { background: #18253d; color: #b4c1d5; border: 0; padding: 8px; font-weight: 700; }
#scanButton { background: #1d4f91; border: 0; border-radius: 7px; color: white; font-weight: 700; padding: 10px 14px; max-width: 210px; } #scanButton:hover { background: #2b65ae; }
#inventory { color: #c9d7eb; font-size: 10pt; line-height: 1.7; }
#legend { color: #59a6ff; font-size: 9pt; } #legend span { color: #31d0aa; } #footer { color: #71829c; font-size: 9pt; } #badge { color: #68d6bb; font-size: 8pt; font-weight: 700; letter-spacing: 1px; padding-top: 18px; }
"""
