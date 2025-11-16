# gui_pyqt6.py
# --------------------------------------------
# GUI for Multi-threaded Download Manager (PyQt6)
# Designed for full async operation with core.DownloadManager
# --------------------------------------------

import sys
import time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QLineEdit, QProgressBar, QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from .core import DownloadManager


class DownloadWorker(QThread):
    """Runs DownloadManager in background thread to avoid GUI freezing"""
    signal_progress = pyqtSignal(float, float, float)  # percent, downloaded_MB, speed_MBps
    signal_status = pyqtSignal(str, str)               # status, message(optional)

    def __init__(self, url: str, filename: str, threads=4, parent=None):
        super().__init__(parent)
        self.url = url
        self.filename = filename
        self.dm = DownloadManager(url, filename, num_threads=threads)
        self._last_time = None
        self._last_downloaded = 0

        # Attach callbacks
        self.dm.progress_callback = self._internal_progress
        self.dm.status_callback = self._internal_status

    def run(self):
        """Starts the download in current thread context"""
        try:
            self.dm.start()
        except Exception as e:
            self.signal_status.emit("error", str(e))

    def _internal_progress(self, percent):
        """Calculate speed and emit signal"""
        now = time.time()
        elapsed = (now - self._last_time) if self._last_time else 0.001
        downloaded_mb = self.dm.downloaded_total / (1024 * 1024)
        speed_mb_s = ((self.dm.downloaded_total - self._last_downloaded) / (1024 * 1024)) / elapsed

        self._last_time = now
        self._last_downloaded = self.dm.downloaded_total

        self.signal_progress.emit(percent, downloaded_mb, speed_mb_s)

    def _internal_status(self, status, message=None):
        """Emit status from core to GUI"""
        self.signal_status.emit(status, message or "")

    def pause(self):
        self.dm.pause_event.set()
        self.signal_status.emit("paused", "")

    def resume(self):
        self.dm.pause_event.clear()
        self.signal_status.emit("resumed", "")

    def stop(self):
        self.dm.stop_event.set()
        self.signal_status.emit("stopped", "")


class DownloadGUI(QWidget):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Download Manager - PyQt6")
        self.setGeometry(400, 250, 500, 240)
        self.worker = None
        self._create_layout()

    def _create_layout(self):
        self.url_label = QLabel("Download URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/file.zip")

        self.start_btn = QPushButton("Start")
        self.pause_btn = QPushButton("Pause")
        self.resume_btn = QPushButton("Resume")
        self.stop_btn = QPushButton("Stop")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)

        self.status_label = QLabel("Status: Idle")
        self.speed_label = QLabel("Speed: 0 MB/s")
        self.downloaded_label = QLabel("Downloaded: 0 MB")

        # button layout
        hbox = QHBoxLayout()
        for b in [self.start_btn, self.pause_btn, self.resume_btn, self.stop_btn]:
            hbox.addWidget(b)

        vbox = QVBoxLayout()
        vbox.addWidget(self.url_label)
        vbox.addWidget(self.url_input)
        vbox.addLayout(hbox)
        vbox.addWidget(self.progress_bar)
        vbox.addWidget(self.status_label)
        vbox.addWidget(self.speed_label)
        vbox.addWidget(self.downloaded_label)

        self.setLayout(vbox)

        # button bindings
        self.start_btn.clicked.connect(self._on_start)
        self.pause_btn.clicked.connect(self._on_pause)
        self.resume_btn.clicked.connect(self._on_resume)
        self.stop_btn.clicked.connect(self._on_stop)

    # --- Button callbacks ---
    def _on_start(self):
        url = self.url_input.text().strip()
        if not url:
            self.status_label.setText("Status: Please provide a valid URL.")
            return

        filename = url.split("/")[-1] or "download.bin"
        self.worker = DownloadWorker(url, filename)
        self.worker.signal_progress.connect(self._on_progress_update)
        self.worker.signal_status.connect(self._on_status_update)
        self.worker.start()

        self.status_label.setText("Status: Starting download...")

    def _on_pause(self):
        if self.worker:
            self.worker.pause()

    def _on_resume(self):
        if self.worker:
            self.worker.resume()

    def _on_stop(self):
        if self.worker:
            self.worker.stop()

    # --- Signal handlers ---
    def _on_progress_update(self, percent, downloaded, speed):
        self.progress_bar.setValue(int(percent))
        self.downloaded_label.setText(f"Downloaded: {downloaded:.2f} MB")
        self.speed_label.setText(f"Speed: {speed:.2f} MB/s")

    def _on_status_update(self, status, message):
        if status == "completed":
            self.status_label.setText("Status: Download completed ✅")
            self.progress_bar.setValue(100)
        elif status == "error":
            self.status_label.setText(f"Status: Error - {message}")
        else:
            self.status_label.setText(f"Status: {status.capitalize()}")


