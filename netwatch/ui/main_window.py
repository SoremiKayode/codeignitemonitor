"""Professional dashboard shell; data comes from the background service."""

from __future__ import annotations

from collections.abc import Callable

from netwatch.core.models import DashboardSnapshot


def format_bytes(value: float, rate: bool = False) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    suffix = "/s" if rate else ""
    return f"{value:.1f} {units[index]}{suffix}"


def create_main_window(snapshot_provider: Callable[[], DashboardSnapshot]):
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QListWidget, QMainWindow, QVBoxLayout, QWidget

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("NetWatch Analyzer")
            self.resize(1160, 720)
            root = QWidget()
            layout = QHBoxLayout(root)
            navigation = QListWidget()
            navigation.addItems(["Dashboard", "Network Usage", "Applications", "Websites", "Connections", "History", "Storage", "Large Files", "Duplicates", "Reports", "Alerts", "Settings", "About"])
            navigation.setFixedWidth(190)
            layout.addWidget(navigation)
            content = QVBoxLayout()
            title = QLabel("NETWORK OVERVIEW")
            title.setObjectName("title")
            content.addWidget(title)
            cards = QHBoxLayout()
            self.download = self._card("DOWNLOAD", "--")
            self.upload = self._card("UPLOAD", "--")
            self.today = self._card("TODAY", "--")
            for card in (self.download, self.upload, self.today): cards.addWidget(card)
            content.addLayout(cards)
            notice = QLabel("Interface-level traffic is active. Per-process traffic and domain attribution require a Windows advanced provider and are labeled separately when available.")
            notice.setWordWrap(True)
            notice.setObjectName("notice")
            content.addWidget(notice)
            chart = QLabel("Real-time traffic chart\n\nMonitoring service is running in the background.\nThe rolling chart is available in the Windows build.")
            chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chart.setObjectName("chart")
            content.addWidget(chart, 1)
            layout.addLayout(content, 1)
            self.setCentralWidget(root)
            timer = QTimer(self)
            timer.timeout.connect(self.refresh)
            timer.start(1000)
            self.refresh()

        def _card(self, label: str, value: str) -> QFrame:
            frame = QFrame()
            frame.setObjectName("card")
            column = QVBoxLayout(frame)
            heading = QLabel(label)
            heading.setObjectName("cardHeading")
            amount = QLabel(value)
            amount.setObjectName("cardValue")
            column.addWidget(heading); column.addWidget(amount)
            frame.amount = amount  # type: ignore[attr-defined]
            return frame

        def refresh(self) -> None:
            snapshot = snapshot_provider()
            self.download.amount.setText(format_bytes(snapshot.download_bytes_per_second, True))  # type: ignore[attr-defined]
            self.upload.amount.setText(format_bytes(snapshot.upload_bytes_per_second, True))  # type: ignore[attr-defined]
            self.today.amount.setText(f"↓ {format_bytes(snapshot.today_download)}\n↑ {format_bytes(snapshot.today_upload)}")  # type: ignore[attr-defined]

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet("""
      QWidget { background: #111827; color: #e5e7eb; font: 10pt 'Segoe UI'; }
      QListWidget { background: #0b1220; border: 0; padding: 12px; outline: 0; }
      QListWidget::item { padding: 10px; border-radius: 6px; } QListWidget::item:selected { background: #1d4ed8; }
      #title { font-size: 20pt; font-weight: 700; padding: 12px 0; } #card { background: #1f2937; border-radius: 10px; min-height: 100px; }
      #cardHeading { color: #93c5fd; font-weight: 700; } #cardValue { font-size: 18pt; font-weight: 700; }
      #notice { background: #172554; color: #bfdbfe; border-radius: 8px; padding: 12px; } #chart { background: #1f2937; border-radius: 10px; color: #9ca3af; }
    """)
    return app, MainWindow()
