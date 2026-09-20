from __future__ import annotations

from collections import deque

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, QSize, Qt
from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QStackedWidget,
    QVBoxLayout, QWidget,
)

from core.downloader import Downloader
from core.library import Library
from ui.downloads_tab import DownloadsTab
from ui.home_tab import HomeTab
from ui.library_tab import LibraryTab
from ui.player_widget import PlayerWidget
from ui.search_tab import SearchTab
from ui.settings_tab import SettingsTab
from ui.toast import ToastManager
from ui.widgets import MotionButton, icon_button, standard_icon


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("iSpotify")
        self.setMinimumSize(840, 580)
        self.resize(1100, 720)
        self.library = Library()
        self.downloader = Downloader()
        self._download_queue = deque()
        self._active_result = None
        self._playback_songs = []
        self._playback_index = -1
        self._nav_buttons = []
        self._page_history = []
        self._current_page = None
        self._playlist_contexts = {}
        self._build()
        self._connect()
        self.navigate("home")

    def _build(self):
        root = QWidget()
        root.setObjectName("appRoot")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.sidebar = self._build_sidebar()
        root_layout.addWidget(self.sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        page_wrap = QWidget()
        page_layout = QVBoxLayout(page_wrap)
        page_layout.setContentsMargins(30, 26, 30, 16)
        page_layout.setSpacing(18)
        self.header = QHBoxLayout()
        self.header.setSpacing(10)
        self.back_button = icon_button("SP_ArrowLeft", "Go back", "backButton")
        self.back_button.clicked.connect(self._go_back)
        self.back_button.setEnabled(False)
        self.header.addWidget(self.back_button)
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        self.page_title = QLabel("Home")
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel("Your music, your way.")
        self.page_subtitle.setObjectName("pageSubtitle")
        title_box.addWidget(self.page_title)
        title_box.addWidget(self.page_subtitle)
        self.header.addLayout(title_box)
        self.header.addStretch()
        page_layout.addLayout(self.header)
        self.pages = QStackedWidget()
        self._pages_opacity = QGraphicsOpacityEffect(self.pages)
        self.pages.setGraphicsEffect(self._pages_opacity)
        self._pages_fade = QPropertyAnimation(
            self._pages_opacity, b"opacity", self
        )
        self._pages_fade.setDuration(180)
        self._pages_fade.setEasingCurve(QEasingCurve.OutQuint)
        self._pages_opacity.setOpacity(1.0)
        self.home = HomeTab(self.library)
        self.search = SearchTab()
        self.library_page = LibraryTab(self.library)
        self.downloads = DownloadsTab()
        self.settings = SettingsTab()
        for page in (self.home, self.search, self.library_page, self.downloads, self.settings):
            self.pages.addWidget(page)
        page_layout.addWidget(self.pages, 1)
        content_layout.addWidget(page_wrap, 1)

        self.player = PlayerWidget()
        content_layout.addWidget(self.player)
        root_layout.addWidget(content, 1)
        self.toast_manager = ToastManager(root)
        self.toast_manager.raise_()
        self.setCentralWidget(root)

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 24, 20, 18)
        layout.setSpacing(4)
        brand_row = QHBoxLayout()
        brand_row.setSpacing(8)
        mark = QLabel("●")
        mark.setStyleSheet("color: #f2f1ec; font-size: 10pt;")
        mark.setFixedWidth(14)
        brand = QLabel("iSpotify")
        brand.setObjectName("brand")
        brand_row.addWidget(mark)
        brand_row.addWidget(brand)
        brand_row.addStretch()
        layout.addLayout(brand_row)
        layout.addSpacing(28)
        for key, label, icon_name in (
            ("home", "Home", "SP_DirHomeIcon"),
            ("search", "Search", "SP_FileDialogContentsView"),
            ("library", "Library", "SP_Library"),
            ("downloading", "Downloads", "SP_ArrowDown"),
            ("settings", "Settings", "SP_Settings"),
        ):
            button = MotionButton(f"  {label}")
            button.setIcon(standard_icon(icon_name))
            button.setIconSize(QSize(16, 16))
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, page=key: self.navigate(page))
            self._nav_buttons.append((key, button))
            layout.addWidget(button)
        layout.addStretch()
        footer = QLabel("© Rubin Labs")
        footer.setObjectName("muted")
        footer.setStyleSheet("font-size: 8pt; letter-spacing: 0.3px;")
        layout.addWidget(footer)
        return sidebar

    def _connect(self):
        self.home.searchRequested.connect(lambda: self.navigate("search"))
        self.home.libraryRequested.connect(lambda: self.navigate("library"))
        self.home.playRequested.connect(self._play_song)
        self.search.downloadRequested.connect(self._on_download_requested)
        self.search.downloadBatchRequested.connect(self._on_download_batch_requested)
        self.search.playlistLoaded.connect(self._on_playlist_loaded)
        self.search.playlistDownloadRequested.connect(
            self._on_playlist_download_requested
        )
        self.library_page.playRequested.connect(self._play_song)
        self.library_page.libraryChanged.connect(self.home.refresh)
        self.downloader.progress.connect(self._on_download_progress)
        self.downloader.downloadFinished.connect(self._on_download_finished)
        self.downloader.downloadFailed.connect(self._on_download_failed)
        self.player.trackChanged.connect(self._on_track_changed)
        self.player.playbackFailed.connect(self._on_playback_failed)
        self.player.headphonesDisconnected.connect(
            self._on_headphones_disconnected
        )
        self.player.previousRequested.connect(self._play_previous)
        self.player.nextRequested.connect(self._play_next)
        self.settings.statusChanged.connect(self._on_settings_status)

    def _on_settings_status(self, message: str):
        kind, _, detail = message.partition("::")
        titles = {
            "success": "Saved", "error": "Couldn't save cookies",
            "warning": "Saved with a download warning", "info": "Done",
        }
        self.toast_manager.show_toast(titles.get(kind, "Settings"), detail, kind)

    def navigate(self, page: str, record_history: bool = True):
        pages = {"home": (self.home, "Home", "Your music, your way."),
                 "search": (self.search, "Search", "Find something worth keeping."),
                 "library": (self.library_page, "Library", "Everything you chose to keep."),
                 "downloading": (self.downloads, "Downloads", "Audio moving into your collection."),
                 "settings": (self.settings, "Settings", "Fix sign-in and bot-check errors.")}
        if page not in pages:
            return
        if (
            record_history
            and self._current_page is not None
            and self._current_page != page
        ):
            self._page_history.append(self._current_page)
        widget, title, subtitle = pages[page]
        self.pages.setCurrentWidget(widget)
        if self._current_page != page:
            self._pages_fade.stop()
            self._pages_fade.setStartValue(0.82)
            self._pages_fade.setEndValue(1.0)
            self._pages_fade.start()
        self.page_title.setText(title)
        self.page_subtitle.setText(subtitle)
        for key, button in self._nav_buttons:
            button.setChecked(key == page)
        self._current_page = page
        self._update_back_button()

    def _go_back(self):
        if self._current_page == "search" and self.search.go_back():
            self._update_back_button()
            return
        if not self._page_history:
            return
        previous_page = self._page_history.pop()
        self.navigate(previous_page, record_history=False)

    def _update_back_button(self):
        self.back_button.setEnabled(
            bool(self._page_history)
            or (
                self._current_page == "search"
                and self.search._current_playlist is not None
            )
        )

    def _play_song(self, song: dict):
        if not song.get("file_path"):
            return
        self._playback_songs = list(reversed(self.library.all_songs()))
        self._playback_index = next(
            (
                index for index, item in enumerate(self._playback_songs)
                if item.get("video_id") == song.get("video_id")
            ),
            -1,
        )
        self.player.load_song(song)
        self._update_player_navigation()
        if song.get("video_id"):
            self.library.mark_played(song["video_id"])
            self.library_page.mark_playing(song["video_id"])
        self.toast_manager.show_toast("Now playing", song.get("title", "Selected track"), "info", 2600)

    def _update_player_navigation(self):
        self.player.set_navigation(
            self._playback_index > 0,
            0 <= self._playback_index < len(self._playback_songs) - 1,
        )

    def _play_previous(self):
        if self._playback_index <= 0:
            return
        self._playback_index -= 1
        self._play_song(self._playback_songs[self._playback_index])

    def _play_next(self):
        if (
            self._playback_index < 0
            or self._playback_index >= len(self._playback_songs) - 1
        ):
            return
        self._playback_index += 1
        self._play_song(self._playback_songs[self._playback_index])

    def _on_track_changed(self, song):
        self.library_page.mark_playing(song.get("video_id", ""))

    def _on_download_requested(self, result):
        self._enqueue_results([result])

    def _on_download_batch_requested(self, results):
        self._enqueue_results(results, batch=True)

    def _on_playlist_loaded(self, playlist):
        first_open = playlist.playlist_id not in self._playlist_contexts
        self._playlist_contexts[playlist.playlist_id] = playlist
        if first_open:
            self.toast_manager.show_toast(
                "Playlist opened",
                f"{playlist.title} · download tracks to keep them in your library.",
                "success",
            )

    def _on_playlist_download_requested(self, playlist, tracks):
        self._playlist_contexts[playlist.playlist_id] = playlist
        self._enqueue_results(tracks, batch=True)

    def _update_downloaded_playlist(self, result):
        playlist_id = getattr(result, "playlist_id", None)
        playlist = self._playlist_contexts.get(playlist_id)
        if not playlist:
            return
        downloaded_tracks = [
            track for track in playlist.tracks
            if self.library.find(track.video_id)
        ]
        if downloaded_tracks:
            self.library.add_playlist(
                playlist.playlist_id,
                playlist.title,
                playlist.channel,
                playlist.thumbnail_url,
                playlist.url,
                downloaded_tracks,
            )

    def _enqueue_results(self, results, batch=False):
        added = []
        skipped = 0
        was_idle = self._active_result is None
        for result in results:
            if self.library.find(result.video_id):
                skipped += 1
                continue
            if (
                self._active_result
                and self._active_result.video_id == result.video_id
            ) or any(item.video_id == result.video_id for item in self._download_queue):
                skipped += 1
                continue
            self._download_queue.append(result)
            added.append(result)

        if not added:
            self.toast_manager.show_toast(
                "Nothing new to download",
                "Those tracks are already saved or already queued.",
                "warning",
            )
            return

        for result in added:
            self.downloads.enqueue(result.title)

        if was_idle:
            self._start_next_download()

        if batch:
            detail = f"{len(added)} tracks added to the queue"
            if skipped:
                detail += f" · {skipped} skipped"
            self.toast_manager.show_toast("Selection queued", detail, "info")
        elif not was_idle:
            self.toast_manager.show_toast(
                "Added to download queue",
                f"{result.title} · {len(self._download_queue)} waiting",
                "info",
            )

    def _start_next_download(self):
        if not self._download_queue:
            self._active_result = None
            return
        self._active_result = self._download_queue.popleft()
        result = self._active_result
        self.downloads.start(result.title)
        self.navigate("downloading")
        self.toast_manager.show_toast("Download started", result.title, "info")
        if not self.downloader.download(result.video_id, result.title):
            self.toast_manager.show_toast(
                "Download could not start",
                "The download worker is still finishing its previous task.",
                "error",
            )
            self._download_queue.appendleft(result)
            self._active_result = None

    def _on_download_progress(self, value: int):
        self.downloads.update_progress(value)

    def _on_download_finished(self, file_path: str):
        result = self._active_result
        self._active_result = None
        if result:
            self.library.add_song(
                result.video_id, result.title, result.channel,
                result.thumbnail_url, file_path,
            )
            self._update_downloaded_playlist(result)
        self.library_page.refresh()
        self.home.refresh()
        self.downloads.finish(True)
        self.toast_manager.show_toast(
            "Download complete",
            f"{result.title if result else 'track'} added to your library.",
            "success",
        )
        QTimer.singleShot(0, self._start_next_download)

    def _on_download_failed(self, message: str):
        result = self._active_result
        self._active_result = None
        self.downloads.finish(False)
        self.toast_manager.show_toast(
            "Download failed",
            f"{result.title if result else 'track'} · {message or 'check your connection and try again.'}",
            "error",
        )
        QTimer.singleShot(0, self._start_next_download)

    def _on_playback_failed(self, message: str):
        self.toast_manager.show_toast(
            "Playback unavailable",
            "That audio file could not be played. Try another track.",
            "error",
        )

    def _on_headphones_disconnected(self, output_name: str, paused: bool):
        if paused:
            detail = "Playback was paused so audio does not switch to speakers."
        elif output_name:
            detail = f"Audio output changed to {output_name}."
        else:
            detail = "No audio output is currently available."
        self.toast_manager.show_toast(
            "Headphones disconnected", detail, "warning"
        )

    def closeEvent(self, event):
        # Release the FFmpeg decoder before Qt tears down the application.
        self.player.close()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "toast_manager"):
            self.toast_manager.setGeometry(self.centralWidget().rect())
