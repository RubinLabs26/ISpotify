from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from ui.widgets import ArtworkLabel, EmptyState, MotionButton, icon_button, standard_icon


class HomeTab(QWidget):
    searchRequested = Signal()
    libraryRequested = Signal()
    playRequested = Signal(object)

    def __init__(self, library):
        super().__init__()
        self.library = library
        self._song_widgets = []
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 24)
        self.root.setSpacing(22)
        self._build()

    def _build(self):
        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(26, 24, 26, 24)
        copy = QVBoxLayout()
        eyebrow = QLabel("your sound, your space")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Music, without the noise.")
        title.setObjectName("pageTitle")
        title.setStyleSheet("font-size: 22pt; letter-spacing: -0.3px; margin-top: 2px;")
        detail = QLabel("Search, save, and listen — kept local.")
        detail.setObjectName("pageSubtitle")
        detail.setWordWrap(True)
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        search = MotionButton("Find music")
        search.setObjectName("accentButton")
        search.clicked.connect(self.searchRequested.emit)
        browse = MotionButton("Browse library")
        browse.clicked.connect(self.libraryRequested.emit)
        action_row.addWidget(search)
        action_row.addWidget(browse)
        action_row.addStretch()
        copy.addWidget(eyebrow)
        copy.addSpacing(6)
        copy.addWidget(title)
        copy.addWidget(detail)
        copy.addSpacing(10)
        copy.addLayout(action_row)
        hero_layout.addLayout(copy)
        hero_layout.addStretch()
        hero_art = QLabel()
        hero_art.setObjectName("heroArtwork")
        hero_art.setFixedSize(QSize(96, 96))
        hero_art.setPixmap(QIcon(
            str(Path(__file__).resolve().parents[1] / "assets" / "hero-art.svg")
        ).pixmap(QSize(96, 96)))
        hero_layout.addWidget(hero_art, 0, Qt.AlignVCenter)
        self.root.addWidget(hero)

        heading = QHBoxLayout()
        label = QLabel("Recently added")
        label.setObjectName("sectionTitle")
        label.setStyleSheet("font-size: 11.5pt;")
        heading.addWidget(label)
        heading.addStretch()
        view_all = MotionButton("View library")
        view_all.setObjectName("ghostButton")
        view_all.clicked.connect(self.libraryRequested.emit)
        heading.addWidget(view_all)
        self.root.addLayout(heading)

        self.song_row = QHBoxLayout()
        self.song_row.setSpacing(14)
        self.root.addLayout(self.song_row)
        self.root.addStretch()
        self.refresh()

    def refresh(self):
        while self.song_row.count():
            item = self.song_row.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        songs = self.library.all_songs()[-4:][::-1]
        if not songs:
            self.song_row.addWidget(EmptyState(
                "Your library is quiet",
                "Download your first song from search and it will appear here.",
            ))
            return
        for song in songs:
            card = self._make_card(song)
            self.song_row.addWidget(card)
        self.song_row.addStretch()

    def _make_card(self, song):
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(180)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)
        artwork_row = QHBoxLayout()
        artwork_row.setContentsMargins(0, 0, 0, 0)
        artwork = ArtworkLabel(
            song["title"], QSize(154, 112), song.get("thumbnail_url", "")
        )
        artwork_row.addWidget(artwork)
        layout.addLayout(artwork_row)
        text = QVBoxLayout()
        text.setSpacing(2)
        title = QLabel(song["title"])
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        title.setMaximumHeight(38)
        artist = QLabel(song.get("channel", "Unknown artist"))
        artist.setObjectName("secondary")
        artist.setWordWrap(True)
        artist.setMaximumHeight(18)
        text.addWidget(title)
        text.addWidget(artist)
        row = QHBoxLayout()
        row.setContentsMargins(0, 4, 0, 0)
        row.addLayout(text, 1)
        play = icon_button("SP_MediaPlay", "Play", "playButton", size=15)
        play.clicked.connect(lambda _checked=False, data=song: self.playRequested.emit(data))
        row.addWidget(play, 0, Qt.AlignBottom)
        layout.addLayout(row)
        return card
