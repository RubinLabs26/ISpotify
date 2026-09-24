"""Visible controls for durable background download jobs."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from ui.widgets import EmptyState, MotionButton, enable_smooth_scroll, standard_icon


class DownloadRow(QFrame):
    actionRequested = Signal(str, str)

    def __init__(self, job: dict, parent=None):
        super().__init__(parent)
        self.video_id = job["video_id"]
        self.setObjectName("downloadCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)
        icon = QLabel()
        icon.setPixmap(standard_icon("SP_AudioArtwork").pixmap(QSize(56, 42)))
        layout.addWidget(icon)
        copy = QVBoxLayout()
        copy.setSpacing(4)
        title = QLabel(job["title"])
        title.setObjectName("sectionTitle")
        title.setWordWrap(True)
        copy.addWidget(title)
        self.status = QLabel()
        self.status.setObjectName("downloadStatus")
        self.status.setWordWrap(True)
        copy.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setObjectName("downloadProgress")
        self.progress.setRange(0, 100)
        self._progress_anim = QPropertyAnimation(self.progress, b"value", self)
        self._progress_anim.setDuration(420)
        self._progress_anim.setEasingCurve(QEasingCurve.OutCubic)
        copy.addWidget(self.progress)
        layout.addLayout(copy, 1)
        actions = QVBoxLayout()
        actions.setSpacing(5)
        state = job["status"]
        primary = {
            "active": ("Pause", "pause"),
            "queued": ("Pause", "pause"),
            "paused": ("Resume", "resume"),
            "failed": ("Retry", "retry"),
        }[state]
        button = MotionButton(primary[0])
        button.setObjectName("ghostButton")
        button.clicked.connect(
            lambda: self.actionRequested.emit(primary[1], self.video_id)
        )
        actions.addWidget(button)
        remove = MotionButton("Remove" if state == "failed" else "Cancel")
        remove.setObjectName("ghostButton")
        remove.clicked.connect(
            lambda: self.actionRequested.emit("cancel", self.video_id)
        )
        actions.addWidget(remove)
        layout.addLayout(actions)
        self.update_job(job)

    def update_job(self, job: dict) -> None:
        value = max(0, min(100, int(job.get("progress") or 0)))
        self.set_progress(value)
        state = job["status"]
        description = {
            "active": "Downloading audio" if value < 100 else "Converting to MP3",
            "queued": "Waiting to download",
            "paused": "Paused — partial download kept",
            "failed": job.get("error") or "Download failed",
        }[state]
        self.status.setText(
            f"{description} · {value}%" if value and state != "failed" else description
        )
        if state == "failed":
            self.status.setToolTip(job.get("error") or "Download failed")

    def set_progress(self, value: int) -> None:
        """Glide forward between progress reports; jump straight back."""
        self._progress_anim.stop()
        # Rows are rebuilt whenever the queue changes; a fresh (hidden) row
        # should show its saved progress at once rather than replay it.
        if value <= self.progress.value() or not self.isVisible():
            self.progress.setValue(value)
            return
        self._progress_anim.setStartValue(self.progress.value())
        self._progress_anim.setEndValue(value)
        self._progress_anim.start()

    def update_transfer(self, percent: int, speed: int, eta: int) -> None:
        self.set_progress(percent)
        if percent >= 100:
            self.status.setText("Converting to MP3")
            return
        detail = [f"{percent}%"]
        if speed:
            rate = f"{speed / 1024 / 1024:.1f} MB/s" if speed >= 1024 * 1024 else f"{speed / 1024:.0f} KB/s"
            detail.append(rate)
        if eta:
            minutes, seconds = divmod(eta, 60)
            detail.append(f"{minutes}:{seconds:02d} remaining" if minutes else f"{seconds}s remaining")
        self.status.setText("Downloading audio · " + " · ".join(detail))


class DownloadsTab(QWidget):
    actionRequested = Signal(str, str)

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 16)
        root.setSpacing(14)

        intro = QFrame()
        intro.setObjectName("downloadIntro")
        intro_layout = QHBoxLayout(intro)
        intro_layout.setContentsMargins(20, 16, 20, 16)
        intro_layout.setSpacing(16)
        icon = QLabel()
        icon.setPixmap(standard_icon("SP_AudioArtwork").pixmap(QSize(56, 42)))
        intro_layout.addWidget(icon)
        copy = QVBoxLayout()
        title = QLabel("Downloads")
        title.setObjectName("sectionTitle")
        detail = QLabel(
            "Queued and paused songs are saved. Interrupted downloads resume when you reopen iSpotify."
        )
        detail.setObjectName("secondary")
        detail.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(detail)
        intro_layout.addLayout(copy, 1)
        root.addWidget(intro)

        self.empty = EmptyState(
            "No downloads", "Save a track from Search to see it here."
        )
        root.addWidget(self.empty, 1)
        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.rows_layout = QVBoxLayout(self.content)
        self.rows_layout.setContentsMargins(0, 0, 8, 0)
        self.rows_layout.setSpacing(10)
        self.scroll.setWidget(self.content)
        enable_smooth_scroll(self.scroll)
        self.scroll.hide()
        root.addWidget(self.scroll, 1)
        self.rows: dict[str, DownloadRow] = {}

    def set_jobs(self, jobs: list[dict]) -> None:
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.rows = {}
        for job in jobs:
            row = DownloadRow(job)
            row.actionRequested.connect(self.actionRequested.emit)
            self.rows_layout.addWidget(row)
            self.rows[job["video_id"]] = row
        self.rows_layout.addStretch()
        self.empty.setVisible(not jobs)
        self.scroll.setVisible(bool(jobs))

    def update_progress(self, video_id: str, value: int) -> None:
        row = self.rows.get(video_id)
        if row:
            row.set_progress(value)
            row.status.setText(
                f"Downloading audio · {value}%" if value < 100
                else "Converting to MP3"
            )

    def update_transfer(self, video_id: str, percent: int, speed: int, eta: int) -> None:
        row = self.rows.get(video_id)
        if row:
            row.update_transfer(percent, speed, eta)
