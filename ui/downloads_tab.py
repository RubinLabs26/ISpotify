from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QVBoxLayout,
    QWidget,
)

from ui.widgets import EmptyState, standard_icon


class DownloadsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(0, 4, 0, 16)
        self.root.setSpacing(14)

        intro = QFrame()
        intro.setObjectName("downloadIntro")
        intro.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        intro_layout = QHBoxLayout(intro)
        intro_layout.setContentsMargins(20, 16, 20, 16)
        intro_layout.setSpacing(16)
        icon = QLabel()
        icon.setPixmap(standard_icon("SP_AudioArtwork").pixmap(QSize(56, 42)))
        intro_layout.addWidget(icon)
        intro_copy = QVBoxLayout()
        intro_copy.setSpacing(2)
        title = QLabel("Downloads")
        title.setObjectName("sectionTitle")
        detail = QLabel("Saved audio appears in Library once it's ready.")
        detail.setObjectName("secondary")
        detail.setWordWrap(True)
        intro_copy.addWidget(title)
        intro_copy.addWidget(detail)
        intro_copy.addStretch()
        intro_layout.addLayout(intro_copy, 1)
        self.root.addWidget(intro)

        self._empty = EmptyState(
            "No active download",
            "Save a track to see its progress here.",
        )
        self.root.addWidget(self._empty)

        self._card = None
        self._queued_titles = []
        self._queue_card = QFrame()
        self._queue_card.setObjectName("downloadQueue")
        self._queue_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        queue_layout = QVBoxLayout(self._queue_card)
        queue_layout.setContentsMargins(14, 11, 14, 11)
        queue_layout.setSpacing(3)
        queue_title = QLabel("Up next")
        queue_title.setObjectName("queueTitle")
        self._queue_label = QLabel("")
        self._queue_label.setObjectName("queueText")
        self._queue_label.setWordWrap(True)
        queue_layout.addWidget(queue_title)
        queue_layout.addWidget(self._queue_label)
        self._queue_card.hide()
        self.root.addWidget(self._queue_card)
        self.root.addStretch()

    def _refresh_queue(self):
        if not self._queued_titles:
            self._queue_label.setText("")
            self._queue_card.hide()
            return
        preview = "  ·  ".join(self._queued_titles[:3])
        extra = max(0, len(self._queued_titles) - 3)
        suffix = f"  ·  +{extra} more" if extra else ""
        self._queue_label.setText(f"{preview}{suffix}")
        self._queue_card.show()

    def start(self, title: str):
        if self._card:
            self._card.deleteLater()
        self._empty.hide()
        if title in self._queued_titles:
            self._queued_titles.remove(title)
        self._refresh_queue()
        self._card = QFrame()
        self._card.setObjectName("downloadCard")
        # Keep the active card compact even when the downloads page is
        # displayed in a maximized or full-screen window.
        self._card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self._card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(16)
        icon = QLabel()
        icon.setPixmap(standard_icon("SP_AudioArtwork").pixmap(QSize(64, 48)))
        layout.addWidget(icon)
        copy = QVBoxLayout()
        copy.setSpacing(4)
        status_row = QHBoxLayout()
        self._title = QLabel(title)
        self._title.setObjectName("sectionTitle")
        status_row.addWidget(self._title, 1)
        self._percent = QLabel("0%")
        self._percent.setObjectName("downloadPercent")
        status_row.addWidget(self._percent)
        self._status = QLabel("Preparing audio…")
        self._status.setObjectName("downloadStatus")
        self._progress = QProgressBar()
        self._progress.setObjectName("downloadProgress")
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        copy.addLayout(status_row)
        copy.addWidget(self._status)
        copy.addSpacing(4)
        copy.addWidget(self._progress)
        layout.addLayout(copy, 1)
        self.root.insertWidget(1, self._card)

    def enqueue(self, title: str):
        self._queued_titles.append(title)
        self._refresh_queue()

    def update_progress(self, value: int):
        if not self._card:
            return
        self._progress.setValue(value)
        self._percent.setText(f"{value}%")
        self._status.setText(f"{value}% downloaded")

    def finish(self, success: bool):
        if not self._card:
            return
        self._status.setText("Added to your library" if success else "Download failed")
        if success:
            self._progress.setValue(100)
            self._percent.setText("100%")
        completed_card = self._card
        self._card = None
        completed_card.deleteLater()
        self._empty.show()
        self._refresh_queue()
