from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from core.library import Library
from ui.widgets import (
    ArtworkLabel, EmptyState, MotionButton, PlaylistArtworkLabel, StatusDot,
    format_duration, icon_button, standard_icon,
)


class LibrarySongCard(QFrame):
    playRequested = Signal(object)
    favoriteRequested = Signal(str)
    renameRequested = Signal(str)
    playlistRequested = Signal(str)
    removeRequested = Signal(str)

    def __init__(self, song, parent=None):
        super().__init__(parent)
        self.song = song
        self.setObjectName("songCard")
        self.setProperty("playing", False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        self.artwork = ArtworkLabel(
            song.get("title", "track"), QSize(64, 48),
            song.get("thumbnail_url", ""),
        )
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
        layout.addSpacing(6)
        video_id = self.song.get("video_id", "")
        organize = icon_button(
            "SP_DirIcon", "Add to playlist", size=16
        )
        organize.clicked.connect(lambda: self.playlistRequested.emit(video_id))
        rename = icon_button(
            "SP_FileDialogDetailedView", "Rename song", size=16
        )
        rename.clicked.connect(lambda: self.renameRequested.emit(video_id))
        play = icon_button("SP_MediaPlay", "Play", "playButton", size=15)
        play.setEnabled(available)
        play.clicked.connect(lambda: self.playRequested.emit(self.song))
        favorite = MotionButton("♥" if song.get("favorite") else "♡")
        favorite.setObjectName("ghostButton")
        favorite.setToolTip("Remove from favorites" if song.get("favorite") else "Add to favorites")
        favorite.clicked.connect(lambda: self.favoriteRequested.emit(video_id))
        remove = icon_button(
            "SP_TrashIcon", "Remove from library", "destructiveButton"
        )
        remove.clicked.connect(lambda: self.removeRequested.emit(video_id))
        layout.addWidget(organize)
        layout.addWidget(rename)
        layout.addWidget(play)
        layout.addWidget(favorite)
        layout.addWidget(remove)

    def set_playing(self, playing: bool):
        self.setProperty("playing", playing)
        self.playing_label.setVisible(playing)
        self.style().unpolish(self)
        self.style().polish(self)


class PlaylistTrackRow(QFrame):
    playRequested = Signal(object)
    renameRequested = Signal(str)
    moveRequested = Signal(str)
    removeRequested = Signal(str)
    orderRequested = Signal(str, int)

    def __init__(
        self, track, song=None, *, can_move=False, can_up=False, can_down=False,
        parent=None,
    ):
        super().__init__(parent)
        self.song = song
        self.setObjectName("songCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(7)
        artwork = ArtworkLabel(
            track.get("title", "track"), QSize(48, 36),
            track.get("thumbnail_url", ""),
        )
        layout.addWidget(artwork)
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
        video_id = track.get("video_id", "")
        up = icon_button("SP_ArrowUp", "Move up", size=14)
        up.setEnabled(can_up)
        up.clicked.connect(lambda: self.orderRequested.emit(video_id, -1))
        down = icon_button("SP_ArrowDown", "Move down", size=14)
        down.setEnabled(can_down)
        down.clicked.connect(lambda: self.orderRequested.emit(video_id, 1))
        move = icon_button("SP_DirIcon", "Move to another playlist", size=15)
        move.setEnabled(can_move)
        move.clicked.connect(lambda: self.moveRequested.emit(video_id))
        rename = icon_button(
            "SP_FileDialogDetailedView", "Rename song", size=15
        )
        rename.clicked.connect(lambda: self.renameRequested.emit(video_id))
        play = icon_button("SP_MediaPlay", "Play", "playButton", size=15)
        play.setEnabled(available)
        if available:
            play.clicked.connect(lambda: self.playRequested.emit(song))
        remove = icon_button(
            "SP_TrashIcon", "Remove from this playlist", "destructiveButton",
            size=15,
        )
        remove.clicked.connect(lambda: self.removeRequested.emit(video_id))
        for button in (up, down, move, rename, play, remove):
            layout.addWidget(button)


class PlaylistLibraryCard(QFrame):
    playRequested = Signal(object)
    renameRequested = Signal(str)
    removeRequested = Signal(str)
    songRenameRequested = Signal(str)
    songMoveRequested = Signal(str, str)
    songRemoveRequested = Signal(str, str)
    songOrderRequested = Signal(str, str, int)

    def __init__(self, playlist, library: Library, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.library = library
        self.setObjectName("card")
        playlist_id = playlist.get("playlist_id", "")
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)
        header = QHBoxLayout()
        header.setSpacing(10)
        artwork = PlaylistArtworkLabel(
            playlist.get("title", "playlist"),
            playlist_id,
            QSize(64, 50),
        )
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
        source = (
            "Local playlist"
            if playlist.get("manual")
            else playlist.get("channel", "YouTube")
        )
        meta = QLabel(
            f"{source}  ·  {downloaded}/{len(tracks)} downloaded"
        )
        meta.setObjectName("secondary")
        copy.addWidget(title)
        copy.addWidget(meta)
        header.addLayout(copy, 1)
        rename = icon_button(
            "SP_FileDialogDetailedView", "Rename playlist", size=16
        )
        rename.clicked.connect(lambda: self.renameRequested.emit(playlist_id))
        header.addWidget(rename)
        self.toggle = icon_button(
            "SP_ChevronDown", f"Show {len(tracks)} tracks", "chevronButton"
        )
        self.toggle.clicked.connect(self._toggle_tracks)
        header.addWidget(self.toggle)
        remove = icon_button(
            "SP_TrashIcon", "Remove playlist", "destructiveButton"
        )
        remove.clicked.connect(lambda: self.removeRequested.emit(playlist_id))
        header.addWidget(remove)
        root.addLayout(header)

        self.track_host = QWidget()
        track_layout = QVBoxLayout(self.track_host)
        track_layout.setContentsMargins(76, 6, 0, 0)
        track_layout.setSpacing(4)
        other_playlists = any(
            item.get("playlist_id") != playlist_id
            for item in self.library.all_playlists()
        )
        if tracks:
            for index, track in enumerate(tracks):
                song = self.library.find(track.get("video_id", ""))
                row = PlaylistTrackRow(
                    track,
                    song,
                    can_move=other_playlists,
                    can_up=index > 0,
                    can_down=index < len(tracks) - 1,
                )
                row.playRequested.connect(self.playRequested.emit)
                row.renameRequested.connect(self.songRenameRequested.emit)
                row.moveRequested.connect(
                    lambda video_id, source=playlist_id:
                    self.songMoveRequested.emit(source, video_id)
                )
                row.removeRequested.connect(
                    lambda video_id, source=playlist_id:
                    self.songRemoveRequested.emit(source, video_id)
                )
                row.orderRequested.connect(
                    lambda video_id, offset, source=playlist_id:
                    self.songOrderRequested.emit(source, video_id, offset)
                )
                track_layout.addWidget(row)
        else:
            empty = QLabel(
                "This playlist is empty. Use the folder button beside a song "
                "to add it."
            )
            empty.setObjectName("muted")
            empty.setWordWrap(True)
            track_layout.addWidget(empty)
        self.track_host.hide()
        root.addWidget(self.track_host)

    def _available(self, video_id):
        song = self.library.find(video_id)
        return bool(song and os.path.exists(song.get("file_path", "")))

    def _toggle_tracks(self):
        visible = not self.track_host.isVisible()
        self.track_host.setVisible(visible)
        count = len(self.playlist.get("tracks", []))
        self.toggle.setIcon(
            standard_icon("SP_ChevronUp" if visible else "SP_ChevronDown")
        )
        self.toggle.setToolTip(
            f"{'Hide' if visible else 'Show'} {count} tracks"
        )


class LibraryTab(QWidget):
    playRequested = Signal(object)
    libraryChanged = Signal()
    songRenamed = Signal(str, str)
    statusChanged = Signal(str)

    def __init__(self, library: Library | None = None):
        super().__init__()
        self.library = library or Library()
        self.cards = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 16)
        root.setSpacing(12)
        controls = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Search your library")
        self.query.textChanged.connect(self.refresh)
        controls.addWidget(self.query, 1)
        self.filter = QComboBox()
        self.filter.addItems(["All songs", "Favorites", "Recently played"])
        self.filter.currentIndexChanged.connect(self.refresh)
        controls.addWidget(self.filter)
        self.sort = QComboBox()
        self.sort.addItems(["Recently added", "Title", "Artist", "Last played", "Most played"])
        self.sort.currentIndexChanged.connect(self.refresh)
        controls.addWidget(self.sort)
        root.addLayout(controls)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.host = QWidget()
        self.list_layout = QVBoxLayout(self.host)
        self.list_layout.setContentsMargins(0, 2, 10, 10)
        self.list_layout.setSpacing(10)
        self.scroll.setWidget(self.host)
        root.addWidget(self.scroll)
        self.refresh()

    def refresh(self):
        self._clear_layout(self.list_layout)
        self.cards = {}

        playlist_heading = QHBoxLayout()
        heading = QLabel("Playlists")
        heading.setObjectName("sectionTitle")
        playlist_heading.addWidget(heading)
        playlist_heading.addStretch()
        create = MotionButton("New playlist")
        create.setObjectName("accentButton")
        create.clicked.connect(self._create_playlist)
        playlist_heading.addWidget(create)
        self.list_layout.addLayout(playlist_heading)

        query = self.query.text().strip().casefold()
        playlists = (
            [playlist for playlist in self.library.all_playlists()
             if query in playlist.get("title", "").casefold()
             or query in playlist.get("channel", "").casefold()]
            if self.filter.currentIndex() == 0 else []
        )
        if playlists:
            for playlist in reversed(playlists):
                card = PlaylistLibraryCard(playlist, self.library)
                card.playRequested.connect(self.playRequested.emit)
                card.renameRequested.connect(self._rename_playlist)
                card.removeRequested.connect(self._remove_playlist)
                card.songRenameRequested.connect(self._rename_song)
                card.songMoveRequested.connect(self._move_song)
                card.songRemoveRequested.connect(self._remove_playlist_song)
                card.songOrderRequested.connect(self._order_playlist_song)
                self.list_layout.addWidget(card)
        elif not query and self.filter.currentIndex() == 0:
            hint = QLabel(
                "Create a playlist, then add downloaded songs with the folder "
                "button."
            )
            hint.setObjectName("muted")
            hint.setWordWrap(True)
            self.list_layout.addWidget(hint)
        self.list_layout.addSpacing(10)

        heading = QLabel("Songs")
        heading.setObjectName("sectionTitle")
        self.list_layout.addWidget(heading)
        songs = self._visible_songs(query)
        if not songs:
            self.list_layout.addWidget(EmptyState(
                "No matching songs" if query or self.filter.currentIndex() else "Your library is quiet",
                "Try another search or filter." if query or self.filter.currentIndex()
                else "Download a song or playlist from search and your collection will live here.",
            ))
        else:
            for song in songs:
                card = LibrarySongCard(song)
                card.playRequested.connect(self.playRequested.emit)
                card.favoriteRequested.connect(self._toggle_favorite)
                card.renameRequested.connect(self._rename_song)
                card.playlistRequested.connect(self._add_song_to_playlist)
                card.removeRequested.connect(self._remove_song)
                self.cards[song.get("video_id", "")] = card
                self.list_layout.addWidget(card)
        self.list_layout.addStretch()

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            nested = item.layout()
            if nested:
                LibraryTab._clear_layout(nested)
                nested.deleteLater()

    def _visible_songs(self, query: str) -> list[dict]:
        songs = self.library.all_songs()
        if self.filter.currentIndex() == 1:
            songs = [song for song in songs if song.get("favorite")]
        elif self.filter.currentIndex() == 2:
            played = {song["video_id"] for song in self.library.recently_played(200)}
            songs = [song for song in songs if song.get("video_id") in played]
        songs = [
            song for song in songs
            if query in song.get("title", "").casefold()
            or query in song.get("channel", "").casefold()
        ]
        sort = self.sort.currentText()
        if sort == "Title":
            songs.sort(key=lambda song: song.get("title", "").casefold())
        elif sort == "Artist":
            songs.sort(key=lambda song: song.get("channel", "").casefold())
        elif sort == "Last played":
            songs.sort(key=lambda song: song.get("last_played") or "", reverse=True)
        elif sort == "Most played":
            songs.sort(key=lambda song: int(song.get("play_count") or 0), reverse=True)
        elif self.filter.currentIndex() == 2:
            songs.sort(key=lambda song: song.get("last_played") or "", reverse=True)
        else:
            songs.reverse()
        return songs

    def _toggle_favorite(self, video_id: str) -> None:
        self.library.toggle_favorite(video_id)
        self.refresh()
        self.libraryChanged.emit()

    def mark_playing(self, video_id: str):
        for key, card in self.cards.items():
            card.set_playing(key == video_id)

    def _create_playlist(self):
        title, accepted = QInputDialog.getText(
            self, "New playlist", "Playlist name:"
        )
        if not accepted or not title.strip():
            return None
        playlist = self.library.create_playlist(title)
        self.refresh()
        self.libraryChanged.emit()
        self.statusChanged.emit(
            f"success::Created playlist “{playlist['title']}”."
        )
        return playlist

    def _rename_playlist(self, playlist_id: str):
        playlist = self.library.find_playlist(playlist_id)
        if not playlist:
            return
        title, accepted = QInputDialog.getText(
            self,
            "Rename playlist",
            "Playlist name:",
            text=playlist.get("title", ""),
        )
        if accepted and self.library.rename_playlist(playlist_id, title):
            self.refresh()
            self.libraryChanged.emit()
            self.statusChanged.emit("success::Playlist renamed.")

    def _rename_song(self, video_id: str):
        song = self.library.find(video_id)
        if not song:
            return
        title, accepted = QInputDialog.getText(
            self,
            "Rename song",
            "Song title:",
            text=song.get("title", ""),
        )
        if accepted and self.library.rename_song(video_id, title):
            clean_title = self.library.find(video_id).get("title", "")
            self.refresh()
            self.libraryChanged.emit()
            self.songRenamed.emit(video_id, clean_title)
            self.statusChanged.emit("success::Song title updated.")

    def _select_playlist(self, source_playlist_id: str | None = None):
        playlists = [
            playlist for playlist in self.library.all_playlists()
            if playlist.get("playlist_id") != source_playlist_id
        ]
        if not playlists:
            if source_playlist_id is not None:
                self.statusChanged.emit(
                    "info::Create another playlist before moving this song."
                )
                return None
            return self._create_playlist()
        choices = [
            f"{playlist.get('title', 'Untitled playlist')} "
            f"({len(playlist.get('tracks', []))} tracks)"
            for playlist in playlists
        ]
        choice, accepted = QInputDialog.getItem(
            self,
            "Choose playlist",
            "Playlist:",
            choices,
            0,
            False,
        )
        if not accepted:
            return None
        return playlists[choices.index(choice)]

    def _add_song_to_playlist(self, video_id: str):
        playlist = self._select_playlist()
        if not playlist:
            return
        if self.library.add_song_to_playlist(
            playlist.get("playlist_id", ""), video_id
        ):
            self.refresh()
            self.libraryChanged.emit()
            self.statusChanged.emit(
                f"success::Added to “{playlist.get('title', 'playlist')}”."
            )
        else:
            self.statusChanged.emit("info::That song is already in the playlist.")

    def _move_song(self, source_playlist_id: str, video_id: str):
        target = self._select_playlist(source_playlist_id)
        if not target:
            return
        if self.library.move_song_to_playlist(
            source_playlist_id, target.get("playlist_id", ""), video_id
        ):
            self.refresh()
            self.libraryChanged.emit()
            self.statusChanged.emit(
                f"success::Moved to “{target.get('title', 'playlist')}”."
            )

    def _order_playlist_song(
        self, playlist_id: str, video_id: str, offset: int
    ):
        if self.library.move_playlist_track(playlist_id, video_id, offset):
            self.refresh()
            self.libraryChanged.emit()

    def _remove_playlist_song(self, playlist_id: str, video_id: str):
        if self.library.remove_song_from_playlist(playlist_id, video_id):
            self.refresh()
            self.libraryChanged.emit()
            self.statusChanged.emit("info::Removed from playlist.")

    def _remove_song(self, video_id: str):
        self.library.remove_song(video_id)
        self.refresh()
        self.libraryChanged.emit()

    def _remove_playlist(self, playlist_id: str):
        self.library.remove_playlist(playlist_id)
        self.refresh()
        self.libraryChanged.emit()
