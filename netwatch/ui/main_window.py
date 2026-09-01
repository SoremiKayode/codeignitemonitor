"""Modern, transparent desktop dashboard driven by the monitoring service.

The UI deliberately distinguishes live interface measurements from features that
need an opt-in advanced Windows provider.  Every navigation item therefore has
an informative screen instead of a blank placeholder or inferred data.
"""

from __future__ import annotations

from collections import deque
from datetime import date, timedelta
from pathlib import Path
from collections.abc import Callable
from typing import Any

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


def create_main_window(service: Any):
    """Build the UI around a MonitoringService (or legacy snapshot callable)."""
    snapshot_provider: Callable[[], DashboardSnapshot] = service.snapshot if hasattr(service, "snapshot") else service
    database = getattr(service, "database", None)
    from PySide6.QtCore import QDate, QTimer, Qt
    from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import (
        QApplication, QCheckBox, QComboBox, QDateEdit, QFileDialog, QFormLayout,
        QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
        QMainWindow, QMessageBox, QPushButton, QSpinBox, QStackedWidget,
        QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
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

    class UsageDonut(QWidget):
        """Circular received/sent visualization for the selected period."""
        def __init__(self) -> None:
            super().__init__(); self.received = self.sent = 0; self.setMinimumSize(260, 260)
        def set_values(self, received: int, sent: int) -> None:
            self.received, self.sent = received, sent; self.update()
        def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
            painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            size = min(self.width(), self.height()) - 50
            ring = self.rect().adjusted((self.width()-size)//2, (self.height()-size)//2, -(self.width()-size)//2, -(self.height()-size)//2)
            painter.setPen(QPen(QColor("#22304b"), 24)); painter.drawEllipse(ring)
            total = self.received + self.sent
            if total:
                painter.setPen(QPen(QColor("#59a6ff"), 24)); painter.drawArc(ring, 90*16, int(-360*16*self.received/total))
                painter.setPen(QPen(QColor("#31d0aa"), 24)); painter.drawArc(ring, int((90-360*self.received/total)*16), int(-360*16*self.sent/total))
            painter.setPen(QColor("#edf3ff")); font=painter.font(); font.setPointSize(18); font.setBold(True); painter.setFont(font)
            painter.drawText(ring, Qt.AlignmentFlag.AlignCenter, format_bytes(total))

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
            self._last_scan = None
            builders = {
                "Overview": self._overview, "Network": self._network_page,
                "Applications": self._applications_page, "Websites": self._websites_page,
                "Connections": self._connections_page, "History": self._history_page,
                "Storage": self._storage_page, "LargeFiles": self._large_files_page,
                "Duplicates": self._duplicates_page, "Reports": self._reports_page,
                "Alerts": self._alerts_page, "Settings": self._settings_page,
                "About": lambda: self._info_page(*PAGE_DETAILS["About"]),
            }
            for _, key in NAVIGATION:
                self.pages.addWidget(builders[key]())
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

        def _range_controls(self, callback) -> QHBoxLayout:
            row = QHBoxLayout(); row.addWidget(QLabel("Period", objectName="fieldLabel"))
            preset = QComboBox(); preset.addItems(["Last 24 hours", "Last 7 days", "Last 30 days", "Custom range"])
            start = QDateEdit(QDate.currentDate().addDays(-6)); end = QDateEdit(QDate.currentDate())
            for control in (start, end): control.setCalendarPopup(True); control.setDisplayFormat("dd MMM yyyy")
            apply = QPushButton("Apply"); apply.setObjectName("primaryButton")
            row.addWidget(preset); row.addWidget(start); row.addWidget(QLabel("to")); row.addWidget(end); row.addWidget(apply); row.addStretch()
            def update_preset(index: int) -> None:
                days=(1,7,30)[index] if index < 3 else None
                if days: start.setDate(QDate.currentDate().addDays(-(days-1))); end.setDate(QDate.currentDate()); callback(start.date().toPython(), end.date().toPython())
            preset.currentIndexChanged.connect(update_preset); apply.clicked.connect(lambda: callback(start.date().toPython(), end.date().toPython()))
            return row

        def _network_page(self) -> QWidget:
            page, column = self._page_shell("Network analytics", "Usage by period", "Compare received and sent traffic for the last day, week, month, or any date range.")
            column.addLayout(self._range_controls(self._load_network_range))
            panel=QFrame(); panel.setObjectName("panel"); row=QHBoxLayout(panel)
            self.usage_donut=UsageDonut(); row.addWidget(self.usage_donut)
            detail=QVBoxLayout(); detail.addWidget(QLabel("SELECTED PERIOD", objectName="panelTitle")); self.range_total=QLabel("No recorded traffic"); self.range_total.setObjectName("heroValue"); detail.addWidget(self.range_total)
            self.range_detail=QLabel("Choose a period to inspect locally recorded interface usage."); self.range_detail.setObjectName("muted"); self.range_detail.setWordWrap(True); detail.addWidget(self.range_detail); detail.addStretch(); row.addLayout(detail, 1)
            column.addWidget(panel,1); QTimer.singleShot(0, lambda: self._load_network_range(date.today()-timedelta(days=6), date.today()))
            return page

        def _load_network_range(self, start: date, end: date) -> None:
            rows = database.usage_between(start, end) if database else []
            received=sum(x[1] for x in rows); sent=sum(x[2] for x in rows); self.usage_donut.set_values(received,sent)
            self.range_total.setText(format_bytes(received+sent)); self.range_detail.setText(f"{start:%d %b %Y} – {end:%d %b %Y}  •  ↓ {format_bytes(received)} received  •  ↑ {format_bytes(sent)} sent  •  {len(rows)} recorded day(s)")

        def _applications_page(self) -> QWidget:
            page, column = self._page_shell("Applications", "Active application activity", "Connection ownership is available now. Per-application bytes require an elevated Windows ETW/WFP collector and are never estimated.")
            notice=QFrame(); notice.setObjectName("disclosure"); nl=QHBoxLayout(notice); nl.addWidget(QLabel("DATA ATTRIBUTION  •  Connection inventory available  •  Consumption requires Administrator capture")); nl.addStretch(); permission=QPushButton("View permission details"); permission.clicked.connect(lambda: QMessageBox.information(self,"Permission required","Windows does not expose reliable per-process byte counters through standard APIs. An audited ETW/WFP collector running as Administrator is required; NetWatch will not silently elevate or invent totals.")); nl.addWidget(permission); column.addWidget(notice)
            self.application_table=QTableWidget(0,4); self.application_table.setHorizontalHeaderLabels(["Application","Active connections","Data consumption","Measurement"]); self._prepare_table(self.application_table); column.addWidget(self.application_table,1)
            return page

        def _websites_page(self) -> QWidget:
            page, column = self._page_shell("Website analytics", "Continuous website consumption", "Hostnames and bytes are measured only for traffic explicitly routed through the local proxy; encrypted page paths and content are not inspected.")
            notice=QFrame(); notice.setObjectName("disclosure"); n=QVBoxLayout(notice); n.addWidget(QLabel("CAPTURE PERMISSION & SETUP", objectName="panelTitle")); n.addWidget(QLabel("Configure the browser HTTP/HTTPS proxy as 127.0.0.1:8787. Browser traffic outside this opt-in route cannot be attributed safely.")); column.addWidget(notice)
            column.addLayout(self._range_controls(self._load_websites))
            self.website_table=QTableWidget(0,4); self.website_table.setHorizontalHeaderLabels(["Website hostname","Received","Sent","Total for selected period"]); self._prepare_table(self.website_table); column.addWidget(self.website_table,1)
            QTimer.singleShot(0, lambda: self._load_websites(date.today()-timedelta(days=6),date.today())); return page

        def _load_websites(self,start:date,end:date)->None:
            rows=database.website_usage_between(start,end) if database else []
            self.website_table.setRowCount(len(rows))
            for r,(domain,received,sent) in enumerate(rows):
                for c,value in enumerate((domain,format_bytes(received),format_bytes(sent),format_bytes(received+sent))): self.website_table.setItem(r,c,QTableWidgetItem(value))

        def _connections_page(self) -> QWidget:
            page,column=self._page_shell("Connections","Live connection details","A readable operating-system inventory of applications, protocols, states, and endpoints; endpoints are not presented as browsing history.")
            carrier=QFrame(); carrier.setObjectName("disclosure"); layout=QVBoxLayout(carrier); layout.addWidget(QLabel("MOBILE NETWORK",objectName="panelTitle")); self.carrier_label=QLabel("Checking Windows mobile broadband…"); layout.addWidget(self.carrier_label); column.addWidget(carrier)
            self.connection_table=QTableWidget(0,5); self.connection_table.setHorizontalHeaderLabels(["Application","Protocol","State","Local endpoint","Remote endpoint"]); self._prepare_table(self.connection_table); column.addWidget(self.connection_table,1); return page

        def _history_page(self)->QWidget:
            page,column=self._page_shell("History","Daily network history","Review the local daily totals that power period comparisons and reports.")
            self.history_table=QTableWidget(0,4); self.history_table.setHorizontalHeaderLabels(["Date","Received","Sent","Total"]); self._prepare_table(self.history_table); column.addWidget(self.history_table,1)
            QTimer.singleShot(0,self._load_history); return page
        def _load_history(self)->None:
            rows=database.usage_between(date.today()-timedelta(days=29),date.today()) if database else []; self.history_table.setRowCount(len(rows))
            for r,(day,down,up) in enumerate(reversed(rows)):
                for c,v in enumerate((day,format_bytes(down),format_bytes(up),format_bytes(down+up))): self.history_table.setItem(r,c,QTableWidgetItem(v))

        def _storage_page(self) -> QWidget:
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
                self._last_scan = result
                groups = find_duplicates(result.files)
                largest = sorted(result.files, key=lambda item: item.size_bytes, reverse=True)[:5]
                types = result.by_extension().most_common(5)
                largest_text = "\n".join(f"{format_bytes(item.size_bytes)} — {item.path.name}" for item in largest) or "No files found"
                types_text = ", ".join(f"{extension}: {format_bytes(size)}" for extension, size in types) or "No file types"
                self.storage_result.setText(f"{len(result.files):,} files · {format_bytes(result.total_bytes)} · {len(result.inaccessible)} inaccessible paths · {len(groups)} duplicate groups\nTop file types: {types_text}\nLargest files:\n{largest_text}")
            button.clicked.connect(scan_folder)
            return page

        def _prepare_table(self, table: QTableWidget) -> None:
            table.setObjectName("usageTable"); table.setAlternatingRowColors(True); table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); table.setSortingEnabled(True); table.horizontalHeader().setStretchLastSection(True); table.verticalHeader().setVisible(False)

        def _large_files_page(self)->QWidget:
            page,column=self._page_shell("Storage insights","Largest files","Scan a folder in Storage, then refresh this ranked view. Files are never changed automatically."); button=QPushButton("Refresh from latest scan"); button.setObjectName("primaryButton"); column.addWidget(button)
            self.large_table=QTableWidget(0,3); self.large_table.setHorizontalHeaderLabels(["File","Type","Size"]); self._prepare_table(self.large_table); column.addWidget(self.large_table,1)
            def load():
                files=sorted(self._last_scan.files,key=lambda x:x.size_bytes,reverse=True)[:100] if self._last_scan else []; self.large_table.setRowCount(len(files))
                for r,item in enumerate(files):
                    for c,v in enumerate((str(item.path),item.path.suffix or "No extension",format_bytes(item.size_bytes))): self.large_table.setItem(r,c,QTableWidgetItem(v))
            button.clicked.connect(load); return page

        def _duplicates_page(self)->QWidget:
            page,column=self._page_shell("Storage insights","Duplicate candidates","Cryptographic comparison confirms equal files. Review candidates here; NetWatch does not delete them."); button=QPushButton("Analyze latest scan"); button.setObjectName("primaryButton"); column.addWidget(button)
            self.duplicate_table=QTableWidget(0,3); self.duplicate_table.setHorizontalHeaderLabels(["Group","File path","Recoverable size"]); self._prepare_table(self.duplicate_table); column.addWidget(self.duplicate_table,1)
            def load():
                groups=find_duplicates(self._last_scan.files) if self._last_scan else []; rows=[(i+1,item.path,item.size_bytes) for i,g in enumerate(groups) for item in g]; self.duplicate_table.setRowCount(len(rows))
                for r,(group,path,size) in enumerate(rows):
                    for c,v in enumerate((str(group),str(path),format_bytes(size))): self.duplicate_table.setItem(r,c,QTableWidgetItem(v))
            button.clicked.connect(load); return page

        def _reports_page(self)->QWidget:
            page,column=self._page_shell("Reports","Export a usage report","Create a CSV summary of locally recorded daily network use for a selected destination."); button=QPushButton("Export last 30 days as CSV"); button.setObjectName("primaryButton"); self.report_status=QLabel("No report exported yet."); column.addWidget(button); column.addWidget(self.report_status); column.addStretch()
            def export():
                path,_=QFileDialog.getSaveFileName(self,"Export report","netwatch-report.csv","CSV files (*.csv)")
                if not path:return
                rows=database.usage_between(date.today()-timedelta(days=29),date.today()) if database else []
                Path(path).write_text("date,received_bytes,sent_bytes,total_bytes\n"+"".join(f"{d},{r},{s},{r+s}\n" for d,r,s in rows),encoding="utf-8"); self.report_status.setText(f"Exported {len(rows)} daily records to {path}")
            button.clicked.connect(export); return page

        def _alerts_page(self)->QWidget:
            page,column=self._page_shell("Alerts","Usage threshold","Set a monthly threshold and see a clear warning when recorded traffic exceeds it."); form=QFrame(); form.setObjectName("panel"); layout=QFormLayout(form); self.alert_limit=QSpinBox(); self.alert_limit.setRange(1,100000); self.alert_limit.setValue(100); self.alert_limit.setSuffix(" GiB"); layout.addRow("Monthly usage threshold",self.alert_limit); self.alert_state=QLabel("Threshold ready."); layout.addRow("Current state",self.alert_state); column.addWidget(form); column.addStretch(); return page

        def _settings_page(self)->QWidget:
            page,column=self._page_shell("Settings","Monitoring preferences","Review collection boundaries and local retention. Changes are written to the user configuration file."); panel=QFrame(); panel.setObjectName("panel"); form=QFormLayout(panel); self.setting_interval=QSpinBox(); self.setting_interval.setRange(1,60); self.setting_interval.setValue(int(getattr(service,"interval",1))); form.addRow("Sampling interval (seconds)",self.setting_interval); domains=QCheckBox("Record hostname totals from opt-in proxy"); domains.setChecked(True); form.addRow("Website collection",domains); save=QPushButton("Save preferences"); save.setObjectName("primaryButton"); form.addRow("",save); self.settings_status=QLabel(""); form.addRow("",self.settings_status); column.addWidget(panel); column.addStretch()
            def persist():
                from netwatch.core.config import SettingsStore
                store=SettingsStore(); settings=store.load(); settings.monitoring_interval_seconds=float(self.setting_interval.value()); settings.monitor_domains=domains.isChecked(); store.save(settings); self.settings_status.setText("Saved. Sampling changes apply after restart.")
            save.clicked.connect(persist); return page

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
            self.chart.append(snapshot.download_bytes_per_second, snapshot.upload_bytes_per_second)
            activity = snapshot.activity
            if activity:
                carrier=activity.carrier; provider=carrier.provider_name or "No mobile carrier reported"; interface=f" • {carrier.interface_name}" if carrier.interface_name else ""; self.carrier_label.setText(f"{provider}{interface}  —  {carrier.source}")
                self.application_table.setSortingEnabled(False); self.application_table.setRowCount(len(activity.applications))
                for row,(name,count) in enumerate(activity.applications):
                    for col,value in enumerate((name,str(count),"Permission required","Connection-only")): self.application_table.setItem(row,col,QTableWidgetItem(value))
                self.application_table.setSortingEnabled(True)
                self.connection_table.setSortingEnabled(False); self.connection_table.setRowCount(len(activity.connections))
                for row,item in enumerate(activity.connections):
                    app=item.process_name or (f"PID {item.pid}" if item.pid else "System / unknown"); local=f"{item.local_address or '—'}:{item.local_port or '—'}"; remote=f"{item.remote_address or '—'}:{item.remote_port or '—'}"
                    for col,value in enumerate((app,item.protocol,item.state or "—",local,remote)): self.connection_table.setItem(row,col,QTableWidgetItem(value))
                self.connection_table.setSortingEnabled(True)
            limit=self.alert_limit.value()*1024**3
            used=snapshot.month_download+snapshot.month_upload
            self.alert_state.setText(f"{'Threshold exceeded' if used >= limit else 'Within threshold'} • {format_bytes(used)} of {self.alert_limit.value()} GiB")

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
#usageTable { alternate-background-color: #101a2d; selection-background-color: #244e80; font: 10pt 'Inter', 'Segoe UI'; background: #141f34; border: 1px solid #22304b; border-radius: 8px; gridline-color: #22304b; } #usageTable::item { padding: 7px; } #usageTable QHeaderView::section { background: #18253d; color: #b4c1d5; border: 0; padding: 8px; font-weight: 700; }
#primaryButton, #scanButton { background: #1d4f91; border: 0; border-radius: 7px; color: white; font-weight: 700; padding: 10px 14px; max-width: 210px; } #primaryButton:hover, #scanButton:hover { background: #2b65ae; }
#inventory { color: #c9d7eb; font-size: 10pt; line-height: 1.7; }
#legend { color: #59a6ff; font-size: 9pt; } #legend span { color: #31d0aa; } #footer { color: #71829c; font-size: 9pt; } #badge { color: #68d6bb; font-size: 8pt; font-weight: 700; letter-spacing: 1px; padding-top: 18px; }
"""
