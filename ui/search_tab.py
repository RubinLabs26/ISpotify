from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from core.searcher import PlaylistResult, Searcher
from ui.widgets import (
    ArtworkLabel, EmptyState, MotionButton, format_duration, icon_button,
    standard_icon,
)


class SearchResultCard(QFrame):
    downloadRequested = Signal(object)
    selectionChanged = Signal(bool)

    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.result = result
        self.selected = False
        self.setObjectName("resultCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 14, 10)
        layout.setSpacing(14)
        self.select_box = QCheckBox()
        self.select_box.setToolTip("Select for batch download")
        self.select_box.stateChanged.connect(self._selection_changed)
        layout.addWidget(self.select_box)
        self.artwork = ArtworkLabel(result.title, QSize(108, 64))
        layout.addWidget(self.artwork)
        text = QVBoxLayout()
        text.setSpacing(3)
        title = QLabel(result.title)
        title.setObjectName("resultTitle")
        title.setWordWrap(True)
        channel = QLabel(f"{result.channel}  ·  {format_duration(result.duration)}")
        channel.setObjectName("secondary")
        text.addWidget(title)
        text.addWidget(channel)
        text.addStretch()
        layout.addLayout(text, 1)
        button = icon_button("SP_DialogSaveButton", "Save to library", "saveButton")
        button.clicked.connect(lambda: self.downloadRequested.emit(self.result))
        layout.addWidget(button)

    def _selection_changed(self, state):
        self.selected = bool(state)
        self.selectionChanged.emit(self.selected)

    def mouseDoubleClickEvent(self, event):
        self.downloadRequested.emit(self.result)
        super().mouseDoubleClickEvent(event)


class PlaylistResultCard(QFrame):
    openRequested = Signal(object)

    def __init__(self, playlist, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.setObjectName("resultCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 14, 10)
        layout.setSpacing(14)
        self.artwork = ArtworkLabel(playlist.title, QSize(108, 78))
        layout.addWidget(self.artwork)
        copy = QVBoxLayout()
        title = QLabel(playlist.title)
        title.setObjectName("resultTitle")
        title.setWordWrap(True)
        owner = QLabel(
            f"{playlist.channel}  ·  "
            f"{playlist.track_count or 'unknown'} tracks"
        )
        owner.setObjectName("secondary")
        copy.addWidget(title)
        copy.addWidget(owner)
        copy.addStretch()
        layout.addLayout(copy, 1)
        button = MotionButton("Open")
        button.setObjectName("accentButton")
        button.setToolTip("Browse tracks in this playlist")
        button.clicked.connect(lambda: self.openRequested.emit(self.playlist))
        layout.addWidget(button)


class PlaylistTrackCard(QFrame):
    downloadRequested = Signal(object)

    def __init__(self, track, parent=None):
        super().__init__(parent)
        self.track = track
        self.setObjectName("songCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        number = QLabel("♪")
        number.setObjectName("muted")
        number.setFixedWidth(16)
        layout.addWidget(number)
        copy = QVBoxLayout()
        title = QLabel(track.title)
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        meta = QLabel(f"{track.channel}  ·  {format_duration(track.duration)}")
        meta.setObjectName("secondary")
        copy.addWidget(title)
        copy.addWidget(meta)
        layout.addLayout(copy, 1)
        button = icon_button("SP_DialogSaveButton", "Save to library", "saveButton")
        button.clicked.connect(lambda: self.downloadRequested.emit(self.track))
        layout.addWidget(button)


class SearchTab(QWidget):
    downloadRequested = Signal(object)
    downloadBatchRequested = Signal(list)
    playlistLoaded = Signal(object)
    playlistDownloadRequested = Signal(object, list)
    statusChanged = Signal(str)

    def __init__(self):
        super().__init__()
        self.searcher = Searcher()
        self.searcher.resultsReady.connect(self._on_results)
        self.searcher.playlistsReady.connect(self._on_playlists)
        self.searcher.playlistReady.connect(self._on_playlist_loaded)
        self.searcher.searchFailed.connect(self._on_error)
        self._cards = []
        self._selected_results = {}
        self._mode = "songs"
        self._current_playlist = None
        self._playlist_results = []
        self._playlist_rendered_count = 0
        self._playlist_header = None
        self._playlist_owner = None
        self._playlist_load_button = None
        self._playlist_download_button = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 16)
        root.setSpacing(12)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(0)
        self.songs_mode = MotionButton("Songs")
        self.playlists_mode = MotionButton("Playlists")
        for button in (self.songs_mode, self.playlists_mode):
            button.setCheckable(True)
            button.setObjectName("modeButton")
            mode_row.addWidget(button)
        self.songs_mode.clicked.connect(lambda: self._set_mode("songs"))
        self.playlists_mode.clicked.connect(lambda: self._set_mode("playlists"))
        mode_row.addStretch()
        root.addLayout(mode_row)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Search songs…")
        self.query_input.setClearButtonEnabled(True)
        self.query_input.returnPressed.connect(self._run_search)
        self.search_button = icon_button(
            "SP_FileDialogContentsView", "Search", "saveButton"
        )
        self.search_button.clicked.connect(self._run_search)
        row.addWidget(self.query_input, 1)
        row.addWidget(self.search_button)
        root.addLayout(row)
        self.status_label = QLabel("Find something worth keeping.")
        self.status_label.setObjectName("muted")
        root.addWidget(self.status_label)

        self.selection_container = QWidget()
        self.selection_row = QHBoxLayout(self.selection_container)
        self.selection_row.setContentsMargins(0, 0, 0, 0)
        self.selection_row.setSpacing(8)
        self.select_all_button = MotionButton("Select all")
        self.select_all_button.setObjectName("ghostButton")
        self.select_all_button.setEnabled(False)
        self.select_all_button.clicked.connect(self._toggle_all)
        self.download_selected_button = MotionButton("Download")
        self.download_selected_button.setObjectName("accentButton")
        self.download_selected_button.setEnabled(False)
        self.download_selected_button.clicked.connect(self._download_selected)
        self.selection_row.addWidget(self.select_all_button)
        self.selection_row.addStretch()
        self.selection_row.addWidget(self.download_selected_button)
        root.addWidget(self.selection_container)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.results_host = QWidget()
        self.results_layout = QVBoxLayout(self.results_host)
        self.results_layout.setContentsMargins(0, 4, 10, 10)
        self.results_layout.setSpacing(8)
        self.results_layout.addWidget(EmptyState(
            "Search the soundtrack",
            "Find songs, or switch to playlists to inspect and save a whole set.",
        ))
        self.results_layout.addStretch()
        self.scroll.setWidget(self.results_host)
        root.addWidget(self.scroll, 1)
        self._set_mode("songs")

    def _set_mode(self, mode: str):
        self._mode = mode
        self.songs_mode.setChecked(mode == "songs")
        self.playlists_mode.setChecked(mode == "playlists")
        self.selection_container.setEnabled(mode == "songs")
        self.selection_container.setVisible(mode == "songs")
        self.query_input.setPlaceholderText(
            "Search playlists…"
            if mode == "playlists" else
            "Search songs…"
        )
        if mode == "playlists":
            self.status_label.setText("Search playlists")
        else:
            self.status_label.setText("Search songs")

    def _clear_results(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        self._cards = []
        self._playlist_rendered_count = 0
        self._playlist_header = None
        self._playlist_owner = None
        self._playlist_load_button = None
        self._playlist_download_button = None
        self._update_selection_actions()

    def _run_search(self):
        query = self.query_input.text().strip()
        if not query:
            self.status_label.setText(
                "Enter a playlist or URL." if self._mode == "playlists"
                else "Enter a song or artist."
            )
            return
        self._current_playlist = None
        if self._mode == "playlists":
            self._playlist_results = []
        self._clear_results()
        self.search_button.setEnabled(False)
        if self._mode == "playlists":
            if "list=" in query:
                playlist_id = query.split("list=", 1)[1].split("&", 1)[0]
                playlist = PlaylistResult(
                    playlist_id, "Loading playlist…", "YouTube", "", query
                )
                self.status_label.setText("Loading playlist tracks…")
                self.searcher.load_playlist(playlist)
                return
            self.status_label.setText(f"Searching playlists for “{query}”…")
            self.statusChanged.emit(f"Searching playlists for “{query}”…")
            self.searcher.search_playlists(query)
        else:
            self.status_label.setText(f"Searching for “{query}”…")
            self.statusChanged.emit(f"Searching for “{query}”…")
            self.searcher.search(query)

    def _on_results(self, results):
        if self._mode != "songs":
            return
        self._clear_results()
        self.search_button.setEnabled(True)
        if not results:
            self.results_layout.addWidget(EmptyState(
                "No matches this time",
                "Try a different spelling or a broader artist search.",
            ))
        for result in results:
            card = SearchResultCard(result)
            card.downloadRequested.connect(self.downloadRequested.emit)
            card.selectionChanged.connect(
                lambda selected, item=card:
                self._on_card_selection_changed(item, selected)
            )
            self._cards.append(card)
            self.results_layout.addWidget(card)
            if result.video_id in self._selected_results:
                card.select_box.setChecked(True)
        self.results_layout.addStretch()
        self.status_label.setText(f"{len(results)} results · choose a track to save")
        self.select_all_button.setEnabled(bool(self._cards))
        self._update_selection_actions()

    def _on_playlists(self, playlists):
        if self._mode != "playlists":
            return
        self._playlist_results = list(playlists)
        self._render_playlist_results(self._playlist_results)

    def _render_playlist_results(self, playlists):
        self._clear_results()
        self.search_button.setEnabled(True)
        if not playlists:
            self.results_layout.addWidget(EmptyState(
                "No playlists found",
                "Try another search.",
            ))
        for playlist in playlists:
            card = PlaylistResultCard(playlist)
            card.openRequested.connect(self._open_playlist)
            self._cards.append(card)
            self.results_layout.addWidget(card)
        self.results_layout.addStretch()
        self.status_label.setText(f"{len(playlists)} playlists")

    def _open_playlist(self, playlist):
        self.status_label.setText(f"Loading “{playlist.title}”…")
        self.searcher.load_playlist(playlist)

    def _on_playlist_loaded(self, playlist):
        self.search_button.setEnabled(True)
        self.playlistLoaded.emit(playlist)
        same_playlist = (
            self._current_playlist is not None
            and self._current_playlist.playlist_id == playlist.playlist_id
        )
        if same_playlist and self._playlist_rendered_count < len(playlist.tracks):
            self._append_playlist_tracks(playlist)
            self._refresh_playlist_controls(playlist)
            self.status_label.setText(
                f"{len(playlist.tracks)} of {playlist.track_count} tracks loaded"
                if playlist.has_more else
                f"{len(playlist.tracks)} tracks · ready to save"
            )
            return

        self._current_playlist = playlist
        self._clear_results()
        header = QFrame()
        header.setObjectName("card")
        self._playlist_header = header
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 14, 14, 14)
        header_layout.setSpacing(14)
        back = icon_button("SP_ArrowLeft", "Back to playlist results", "backButton")
        back.clicked.connect(self._restore_playlist_search)
        header_layout.addWidget(back, 0, Qt.AlignTop)
        artwork = ArtworkLabel(playlist.title, QSize(140, 100))
        header_layout.addWidget(artwork)
        copy = QVBoxLayout()
        title = QLabel(playlist.title)
        title.setObjectName("sectionTitle")
        title.setWordWrap(True)
        owner = QLabel(
            f"{playlist.channel}  ·  {len(playlist.tracks)} tracks"
        )
        owner.setObjectName("secondary")
        self._playlist_owner = owner
        copy.addWidget(title)
        copy.addWidget(owner)
        copy.addStretch()
        header_layout.addLayout(copy, 1)
        actions = QVBoxLayout()
        actions.setSpacing(6)
        self._playlist_load_button = MotionButton("Load more")
        self._playlist_load_button.clicked.connect(self._load_more_playlist)
        download_all = MotionButton("Download all")
        download_all.setObjectName("accentButton")
        download_all.clicked.connect(
            lambda: self.playlistDownloadRequested.emit(
                playlist, list(playlist.tracks)
            )
        )
        self._playlist_download_button = download_all
        actions.addWidget(self._playlist_load_button)
        actions.addWidget(download_all)
        actions.addStretch()
        header_layout.addLayout(actions)
        self.results_layout.addWidget(header)

        label = QLabel("Tracks in this playlist")
        label.setObjectName("sectionTitle")
        self.results_layout.addWidget(label)
        if not playlist.tracks:
            self.results_layout.addWidget(EmptyState(
                "This playlist is empty",
                "YouTube did not return any playable entries.",
            ))
        # The stretch must exist before tracks are inserted: _append_playlist_tracks
        # always inserts just above the layout's final item, which is meant to be
        # this stretch (not the heading label above).
        self.results_layout.addStretch()
        self._append_playlist_tracks(playlist)
        self._refresh_playlist_controls(playlist)
        self.status_label.setText(
            f"{len(playlist.tracks)} of {playlist.track_count} tracks loaded"
            if playlist.has_more else
            f"{len(playlist.tracks)} tracks · ready to save"
        )

    def _append_playlist_tracks(self, playlist):
        new_tracks = playlist.tracks[self._playlist_rendered_count:]
        for track in new_tracks:
            card = PlaylistTrackCard(track)
            card.downloadRequested.connect(self.downloadRequested.emit)
            self.results_layout.insertWidget(
                self.results_layout.count() - 1, card
            )
        self._playlist_rendered_count = len(playlist.tracks)

    def _refresh_playlist_controls(self, playlist):
        if self._playlist_owner:
            self._playlist_owner.setText(
                f"{playlist.channel}  ·  "
                f"{len(playlist.tracks)} of {playlist.track_count} tracks"
                if playlist.has_more else
                f"{playlist.channel}  ·  {len(playlist.tracks)} tracks"
            )
        if self._playlist_load_button:
            self._playlist_load_button.setVisible(playlist.has_more)
            self._playlist_load_button.setEnabled(True)
            self._playlist_load_button.setText(
                f"Load {min(50, playlist.track_count - len(playlist.tracks))} more"
                if playlist.track_count > len(playlist.tracks)
                else "Load more"
            )
        if self._playlist_download_button:
            self._playlist_download_button.setText(
                "Download loaded" if playlist.has_more else "Download all"
            )

    def _load_more_playlist(self):
        playlist = self._current_playlist
        if not playlist or not playlist.has_more:
            return
        self._playlist_load_button.setEnabled(False)
        self._playlist_load_button.setText("Loading…")
        self.status_label.setText(
            f"Loading tracks {len(playlist.tracks) + 1}–"
            f"{min(playlist.track_count, len(playlist.tracks) + 50)}…"
        )
        self.searcher.load_playlist(
            playlist,
            start=playlist.next_start,
        )

    def _restore_playlist_search(self):
        self._current_playlist = None
        if self._playlist_results:
            self._render_playlist_results(self._playlist_results)
        else:
            self._clear_results()
            self.results_layout.addWidget(EmptyState(
                "Search playlists",
                "Search for a playlist.",
            ))
            self.results_layout.addStretch()
            self.search_button.setEnabled(True)
            self.status_label.setText("Search playlists")

    def go_back(self) -> bool:
        """Return to playlist results when a playlist detail view is open."""
        if self._current_playlist is None:
            return False
        self._restore_playlist_search()
        return True

    def _update_selection_actions(self):
        selected_count = len(self._selected_results)
        self.download_selected_button.setEnabled(selected_count > 0)
        self.download_selected_button.setText(
            f"Download · {selected_count}"
            if selected_count else "Download"
        )
        if self._cards and self._mode == "songs":
            visible_selected = sum(
                card.result.video_id in self._selected_results
                for card in self._cards if hasattr(card, "result")
            )
            self.select_all_button.setText(
                "Clear selection"
                if visible_selected == len(self._cards) else "Select all"
            )

    def _toggle_all(self):
        select = any(
            card.result.video_id not in self._selected_results
            for card in self._cards if hasattr(card, "result")
        )
        for card in self._cards:
            if not hasattr(card, "result"):
                continue
            card.select_box.setChecked(select)
            if select:
                self._selected_results[card.result.video_id] = card.result
            else:
                self._selected_results.pop(card.result.video_id, None)
        self._update_selection_actions()

    def _download_selected(self):
        selected = list(self._selected_results.values())
        if selected:
            self.downloadBatchRequested.emit(selected)
            self._selected_results.clear()
            for card in self._cards:
                if hasattr(card, "selected") and card.selected:
                    card.select_box.setChecked(False)
            self._update_selection_actions()

    def _on_card_selection_changed(self, card, selected: bool):
        if selected:
            self._selected_results[card.result.video_id] = card.result
        else:
            self._selected_results.pop(card.result.video_id, None)
        self._update_selection_actions()

    def _on_error(self, message):
        self.search_button.setEnabled(True)
        self._clear_results()
        self.results_layout.addWidget(EmptyState(
            "Search is unavailable",
            "We couldn't reach YouTube right now. Check your connection and try again.",
        ))
        self.results_layout.addStretch()
        self.status_label.setText("Search failed")
        self.statusChanged.emit("Search failed")
