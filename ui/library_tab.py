from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from core.library import Library
from ui.widgets import (
    ArtworkLabel, EmptyState, MotionButton, StatusDot, format_duration,
    icon_button, standard_icon,
)


class LibrarySongCard(QFrame):
    playRequested = Signal(object)
    removeRequested = Signal(str)

    def __init__(self, song, parent=None):
        super().__init__(parent)
        self.song = song
        self.setObjectName("songCard")
        self.setProperty("playing", False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(14)
        self.artwork = ArtworkLabel(song.get("title", "track"), QSize(64, 48))
        layout.addWidget(self.artwork)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        title = QLabel(song.get("title", "Unknown title"))
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        artist = QLabel(song.get("channel", "Unknown artist"))
        artist.setObjectName("secondary")
        copy.addWidget(title)
        copy.addWidget(artist)
        layout.addLayout(copy, 1)
        self.playing_label = QLabel("playing")
        self.playing_label.setObjectName("playingPill")
        self.playing_label.hide()
        layout.addWidget(self.playing_label)
        file_path = song.get("file_path", "")
        available = bool(file_path and os.path.exists(file_path))
        self.status_dot = StatusDot(available, "Available offline", "File missing")
        layout.addWidget(self.status_dot)
        play = icon_button("SP_MediaPlay", "Play", "playButton", size=15)
        play.setEnabled(available)
        play.clicked.connect(lambda: self.playRequested.emit(self.song))
        remove = icon_button("SP_TrashIcon", "Remove from library", "destructiveButton")
        remove.clicked.connect(lambda: self.removeRequested.emit(
            self.song.get("video_id", "")
        ))
        layout.addWidget(play)
        layout.addWidget(remove)

    def set_playing(self, playing: bool):
        self.setProperty("playing", playing)
        self.playing_label.setVisible(playing)
        self.style().unpolish(self)
        self.style().polish(self)


class PlaylistTrackRow(QFrame):
    playRequested = Signal(object)

    def __init__(self, track, song=None, parent=None):
        super().__init__(parent)
        self.song = song
        self.setObjectName("songCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(10)
        copy = QVBoxLayout()
        copy.setSpacing(1)
        title = QLabel(track.get("title", "Unknown title"))
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        meta = QLabel(
            f"{track.get('channel', 'Unknown artist')}  ·  "
            f"{format_duration(track.get('duration', 0))}"
        )
        meta.setObjectName("secondary")
        copy.addWidget(title)
        copy.addWidget(meta)
        layout.addLayout(copy, 1)
        available = bool(song and os.path.exists(song.get("file_path", "")))
        layout.addWidget(StatusDot(available, "Downloaded", "Not downloaded"))
        play = icon_button("SP_MediaPlay", "Play", "playButton", size=15)
        play.setEnabled(available)
        if available:
            play.clicked.connect(lambda: self.playRequested.emit(song))
        layout.addWidget(play)


class PlaylistLibraryCard(QFrame):
    playRequested = Signal(object)
    removeRequested = Signal(str)

    def __init__(self, playlist, library: Library, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.library = library
        self.setObjectName("card")
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)
        header = QHBoxLayout()
        header.setSpacing(12)
        artwork = ArtworkLabel(playlist.get("title", "playlist"), QSize(64, 50))
        header.addWidget(artwork)
        self.artwork = artwork
        copy = QVBoxLayout()
        copy.setSpacing(2)
        title = QLabel(playlist.get("title", "Untitled playlist"))
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        tracks = playlist.get("tracks", [])
        downloaded = sum(
            1 for track in tracks
            if self._available(track.get("video_id", ""))
        )
        meta = QLabel(
            f"{playlist.get('channel', 'YouTube')}  ·  "
            f"{downloaded}/{len(tracks)} downloaded"
        )
        meta.setObjectName("secondary")
        copy.addWidget(title)
        copy.addWidget(meta)
        header.addLayout(copy, 1)
        self.toggle = icon_button("SP_ChevronDown", f"Show {len(tracks)} tracks", "chevronButton")
        self.toggle.clicked.connect(self._toggle_tracks)
        header.addWidget(self.toggle)
        remove = icon_button("SP_TrashIcon", "Remove playlist", "destructiveButton")
        remove.clicked.connect(lambda: self.removeRequested.emit(
            playlist.get("playlist_id", "")
        ))
        header.addWidget(remove)
        root.addLayout(header)

        self.track_host = QWidget()
        track_layout = QVBoxLayout(self.track_host)
        track_layout.setContentsMargins(76, 6, 0, 0)
        track_layout.setSpacing(4)
        for track in tracks:
            song = self.library.find(track.get("video_id", ""))
            row = PlaylistTrackRow(track, song)
            row.playRequested.connect(self.playRequested.emit)
            track_layout.addWidget(row)
        self.track_host.hide()
        root.addWidget(self.track_host)

    def _available(self, video_id):
        song = self.library.find(video_id)
        return bool(song and os.path.exists(song.get("file_path", "")))

    def _toggle_tracks(self):
        visible = not self.track_host.isVisible()
        self.track_host.setVisible(visible)
        count = len(self.playlist.get("tracks", []))
        self.toggle.setIcon(standard_icon("SP_ChevronUp" if visible else "SP_ChevronDown"))
        self.toggle.setToolTip(f"{'Hide' if visible else 'Show'} {count} tracks")


class LibraryTab(QWidget):
    playRequested = Signal(object)
    libraryChanged = Signal()

    def __init__(self, library: Library | None = None):
        super().__init__()
        self.library = library or Library()
        self.cards = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 16)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.host = QWidget()
        self.list_layout = QVBoxLayout(self.host)
        self.list_layout.setContentsMargins(0, 5, 10, 10)
        self.list_layout.setSpacing(8)
        self.scroll.setWidget(self.host)
        root.addWidget(self.scroll)
        self.refresh()

    def refresh(self):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        self.cards = {}

        playlists = self.library.all_playlists()
        if playlists:
            heading = QLabel("Playlists")
            heading.setObjectName("sectionTitle")
            self.list_layout.addWidget(heading)
            for playlist in reversed(playlists):
                card = PlaylistLibraryCard(playlist, self.library)
                card.playRequested.connect(self.playRequested.emit)
                card.removeRequested.connect(self._remove_playlist)
                self.list_layout.addWidget(card)
            self.list_layout.addSpacing(10)

        heading = QLabel("Songs")
        heading.setObjectName("sectionTitle")
        self.list_layout.addWidget(heading)
        songs = self.library.all_songs()
        if not songs:
            self.list_layout.addWidget(EmptyState(
                "Your library is quiet",
                "Download a song or playlist from search and your collection will live here.",
            ))
        else:
            for song in reversed(songs):
                card = LibrarySongCard(song)
                card.playRequested.connect(self.playRequested.emit)
                card.removeRequested.connect(self._remove_song)
                self.cards[song.get("video_id", "")] = card
                self.list_layout.addWidget(card)
        self.list_layout.addStretch()

    def mark_playing(self, video_id: str):
        for key, card in self.cards.items():
            card.set_playing(key == video_id)

    def _remove_song(self, video_id: str):
        self.library.remove_song(video_id)
        self.refresh()
        self.libraryChanged.emit()

    def _remove_playlist(self, playlist_id: str):
        self.library.remove_playlist(playlist_id)
        self.refresh()
        self.libraryChanged.emit()
