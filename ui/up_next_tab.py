"""Visible session playback queue with drag ordering and quick actions."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QVBoxLayout, QWidget,
)

from ui.widgets import MotionButton


class UpNextTab(QWidget):
    playAtRequested = Signal(int)
    removeAtRequested = Signal(int)
    clearRequested = Signal()
    orderChanged = Signal(list)

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 16)
        root.setSpacing(12)
        self.now_playing = QLabel("Nothing playing")
        self.now_playing.setObjectName("sectionTitle")
        root.addWidget(self.now_playing)
        hint = QLabel("Drag songs to reorder what plays next.")
        hint.setObjectName("secondary")
        root.addWidget(hint)
        self.list = QListWidget()
        self.list.setObjectName("upNextList")
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.itemDoubleClicked.connect(lambda _item: self._play_selected())
        self.list.model().rowsMoved.connect(self._order_changed)
        root.addWidget(self.list, 1)
        actions = QHBoxLayout()
        play = MotionButton("Play selected")
        play.setObjectName("accentButton")
        play.clicked.connect(self._play_selected)
        actions.addWidget(play)
        remove = MotionButton("Remove selected")
        remove.clicked.connect(self._remove_selected)
        actions.addWidget(remove)
        actions.addStretch()
        clear = MotionButton("Clear Up Next")
        clear.clicked.connect(self.clearRequested.emit)
        actions.addWidget(clear)
        root.addLayout(actions)

    def set_queue(self, current: str | None, upcoming: list[str], library) -> None:
        song = library.find(current) if current else None
        self.now_playing.setText(
            f"Now playing: {song.get('title', 'Unknown title')}" if song else "Nothing playing"
        )
        self.list.blockSignals(True)
        self.list.clear()
        for video_id in upcoming:
            song = library.find(video_id)
            item = QListWidgetItem(
                f"{song.get('title', 'Unknown title')}  ·  {song.get('channel', '')}"
                if song else f"Unavailable track · {video_id}"
            )
            item.setData(Qt.UserRole, video_id)
            self.list.addItem(item)
        self.list.blockSignals(False)

    def _play_selected(self) -> None:
        if self.list.currentRow() >= 0:
            self.playAtRequested.emit(self.list.currentRow())

    def _remove_selected(self) -> None:
        if self.list.currentRow() >= 0:
            self.removeAtRequested.emit(self.list.currentRow())

    def _order_changed(self, *_args) -> None:
        self.orderChanged.emit([
            self.list.item(index).data(Qt.UserRole)
            for index in range(self.list.count())
        ])
