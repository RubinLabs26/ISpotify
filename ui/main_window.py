from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QProcess, QPropertyAnimation, QTimer, QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QMessageBox
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QStackedWidget,
    QVBoxLayout, QWidget,
)

from core.downloader import Downloader, discard_download_files, explain_download_error
from core.download_state import DownloadState, result_from_job
from core.discord_presence import DiscordPresence
from core.library import Library
from core.playback_queue import PlaybackQueue
from core.update_install import (
    install_linux_portable, install_mode, install_windows,
    install_windows_portable, restart_application,
)
from core.updater import RELEASE_PAGE, UpdateManager
from core.version import APP_VERSION
from ui.downloads_tab import DownloadsTab
from ui.home_tab import HomeTab
from ui.library_tab import LibraryTab
from ui.player_widget import PlayerWidget
from ui.search_tab import SearchTab
from ui.settings_tab import SettingsTab
from ui.up_next_tab import UpNextTab
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
        self.download_state = DownloadState()
        self._active_result = None
        self._shutting_down = False
        self._cancel_requested_ids = set()
        self.playback_queue = PlaybackQueue()
        self._nav_buttons = []
        self._page_history = []
        self._current_page = None
        self._playlist_contexts = self.download_state.playlist_contexts()
        for job in list(self.download_state.jobs):
            if self.library.find(job["video_id"]):
                self.download_state.remove(job["video_id"])
        self._build()
        self.downloads.set_jobs(self.download_state.jobs)
        self.discord_presence = DiscordPresence(self)
        self.updater = UpdateManager(self)
        self._update_version = ""
        self._package_install = None
        self._discord_refresh_timer = QTimer(self)
        self._discord_refresh_timer.setInterval(30_000)
        self._discord_refresh_timer.timeout.connect(self._sync_discord_presence)
        self._connect()
        self._configure_discord(self.settings.discord_config())
        self.navigate("home")
        QTimer.singleShot(3000, self.updater.check)
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(6 * 60 * 60 * 1000)
        self._update_timer.timeout.connect(self.updater.check)
        self._update_timer.start()
        QTimer.singleShot(0, self._start_next_download)

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
        self.update_button = MotionButton("Update available")
        self.update_button.setObjectName("accentButton")
        self.update_button.clicked.connect(lambda: self.navigate("settings"))
        self.update_button.hide()
        self.header.addWidget(self.update_button)
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
        self.up_next = UpNextTab()
        self.settings = SettingsTab()
        for page in (self.home, self.search, self.library_page, self.downloads, self.up_next, self.settings):
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
            ("up_next", "Up Next", "SP_MediaSeekForward"),
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
        self.home.favoritesRequested.connect(lambda: self._open_library_filter(1))
        self.home.historyRequested.connect(lambda: self._open_library_filter(2))
        self.home.playRequested.connect(self._play_song)
        self.search.downloadRequested.connect(self._on_download_requested)
        self.search.downloadBatchRequested.connect(self._on_download_batch_requested)
        self.search.playlistLoaded.connect(self._on_playlist_loaded)
        self.search.playlistDownloadRequested.connect(
            self._on_playlist_download_requested
        )
        self.library_page.playRequested.connect(self._play_song)
        self.library_page.playNextRequested.connect(self._play_next_requested)
        self.library_page.libraryChanged.connect(self.home.refresh)
        self.library_page.libraryChanged.connect(self._refresh_up_next)
        self.library_page.songRenamed.connect(self._on_song_renamed)
        self.library_page.statusChanged.connect(self._on_library_status)
        self.downloader.progress.connect(self._on_download_progress)
        self.downloader.transfer.connect(self._on_download_transfer)
        self.downloader.downloadFinished.connect(self._on_download_finished)
        self.downloader.downloadFailed.connect(self._on_download_failed)
        self.downloader.downloadCancelled.connect(self._on_download_cancelled)
        self.downloads.actionRequested.connect(self._on_download_action)
        self.player.trackChanged.connect(self._on_track_changed)
        self.player.playbackFailed.connect(self._on_playback_failed)
        self.player.player.playbackStateChanged.connect(
            self._on_playback_state_changed
        )
        self.player.headphonesDisconnected.connect(
            self._on_headphones_disconnected
        )
        self.player.previousRequested.connect(self._play_previous)
        self.player.nextRequested.connect(self._play_next)
        self.player.queueRequested.connect(lambda: self.navigate("up_next"))
        self.player.shuffleRequested.connect(self._toggle_shuffle)
        self.player.repeatRequested.connect(self._cycle_repeat)
        self.player.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.up_next.playAtRequested.connect(self._play_queued_index)
        self.up_next.removeAtRequested.connect(self._remove_queued_index)
        self.up_next.clearRequested.connect(self._clear_up_next)
        self.up_next.orderChanged.connect(self._reorder_up_next)
        self.settings.statusChanged.connect(self._on_settings_status)
        self.settings.discordStatusChanged.connect(self._on_discord_ui_status)
        self.settings.discordChanged.connect(self._configure_discord)
        self.settings.discordLoginRequested.connect(self.discord_presence.login)
        self.settings.discordLogoutRequested.connect(self.discord_presence.logout)
        self.discord_presence.authorizationUrlReady.connect(
            self.settings.open_discord_authorization
        )
        self.discord_presence.statusChanged.connect(
            self.settings.set_discord_status
        )
        self.discord_presence.accountChanged.connect(
            self.settings.set_discord_account
        )
        self.settings.updateCheckRequested.connect(self.updater.check)
        self.settings.updateInstallRequested.connect(self._install_update)
        self.updater.checkStarted.connect(
            lambda: self.settings.set_update_status("Checking for updates…", checking=True)
        )
        self.updater.updateAvailable.connect(self._on_update_available)
        self.updater.upToDate.connect(self._on_up_to_date)
        self.updater.failed.connect(self._on_update_failed)
        self.updater.downloadProgress.connect(self._on_update_progress)
        self.updater.downloadReady.connect(self._on_update_ready)

    def _on_update_available(self, version: str) -> None:
        first_notice = self._update_version != version
        self._update_version = version
        self.update_button.show()
        action = "Download and install" if self.updater.asset else "Open download page"
        self.settings.update_install_button.setText(action)
        self.settings.set_update_status(
            f"v{version} is available. Installed: v{APP_VERSION}.", available=True
        )
        if first_notice:
            self.toast_manager.show_toast(
                "Update available", f"iSpotify v{version} is ready.", "info"
            )

    def _on_up_to_date(self) -> None:
        self._update_version = ""
        self.update_button.hide()
        self.settings.set_update_status(f"You're up to date: v{APP_VERSION}.")

    def _on_update_failed(self, message: str) -> None:
        self.settings.set_update_status(message, available=bool(self._update_version))

    def _on_update_progress(self, received: int, total: int) -> None:
        if total > 0:
            percent = min(100, max(0, round(received * 100 / total)))
            self.settings.set_update_status(
                f"Downloading v{self._update_version}: {percent}%",
                checking=True,
            )

    def _install_update(self) -> None:
        if not self.updater.asset:
            QDesktopServices.openUrl(QUrl(RELEASE_PAGE))
            return
        self.settings.set_update_status(
            f"Downloading v{self._update_version}…", checking=True
        )
        self.updater.download()

    def _on_update_ready(self, path: str) -> None:
        from pathlib import Path

        package = Path(path)
        mode = install_mode()
        try:
            if mode == "windows-installer":
                self.settings.set_update_status("Installing update. iSpotify will close.")
                install_windows(package)
                QApplication.quit()
            elif mode == "windows-portable":
                self.settings.set_update_status("Installing update. iSpotify will close.")
                install_windows_portable(package)
                QApplication.quit()
            elif mode == "linux-portable":
                install_linux_portable(package)
                self._ask_restart()
            elif mode == "debian-package":
                self.settings.set_update_status("Installing update…", checking=True)
                self._package_install = QProcess(self)
                self._package_install.finished.connect(self._on_package_installed)
                self._package_install.start("pkexec", ["dpkg", "-i", str(package)])
            else:
                target = package if package.suffix == ".deb" else package.parent
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
                guidance = (
                    "Open it with your package manager."
                    if package.suffix == ".deb"
                    else "Replace your portable executable or use your package manager."
                )
                self.settings.set_update_status(
                    f"Update downloaded to {package}. {guidance}"
                )
        except OSError as exc:
            self._on_update_failed(f"Could not install update: {exc}")

    def _on_package_installed(self, exit_code: int, _status) -> None:
        if exit_code == 0:
            self._ask_restart()
        else:
            self._on_update_failed(
                "Package installation was cancelled or failed. Try your package manager."
            )

    def _ask_restart(self) -> None:
        self.settings.set_update_status(
            "Update installed. Restart iSpotify to use the new version."
        )
        answer = QMessageBox.question(
            self,
            "Update installed",
            "iSpotify was updated successfully. Restart now to use the new version?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            restart_application()
            QApplication.quit()

    def _on_settings_status(self, message: str):
        kind, _, detail = message.partition("::")
        titles = {
            "success": "Saved", "error": "Couldn't save cookies",
            "warning": "Saved with a download warning", "info": "Done",
        }
        self.toast_manager.show_toast(titles.get(kind, "Settings"), detail, kind)

    def _on_library_status(self, message: str):
        kind, _, detail = message.partition("::")
        titles = {
            "success": "Library updated",
            "error": "Library update failed",
            "warning": "Library warning",
            "info": "Library",
        }
        self.toast_manager.show_toast(
            titles.get(kind, "Library"), detail, kind
        )

    def _on_discord_ui_status(self, message: str):
        kind, _, detail = message.partition("::")
        self.toast_manager.show_toast(
            "Discord authorization", detail, kind
        )

    def _on_song_renamed(self, video_id: str, _title: str):
        self._refresh_up_next()
        if (
            self.player.current_song
            and self.player.current_song.get("video_id") == video_id
        ):
            self.player.refresh_song_metadata()
            self._sync_discord_presence()

    def _open_library_filter(self, index: int) -> None:
        self.library_page.filter.setCurrentIndex(index)
        self.navigate("library")

    def navigate(self, page: str, record_history: bool = True):
        pages = {"home": (self.home, "Home", "Your music, your way."),
                 "search": (self.search, "Search", "Find something worth keeping."),
                 "library": (self.library_page, "Library", "Everything you chose to keep."),
                 "downloading": (self.downloads, "Downloads", "Audio moving into your collection."),
                 "up_next": (self.up_next, "Up Next", "Choose what plays after this song."),
                 "settings": (self.settings, "Settings", "Connections and privacy controls.")}
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
        context = [item["video_id"] for item in reversed(self.library.all_songs())]
        self.playback_queue.start(song.get("video_id", ""), context)
        self._load_queued_song(song)

    def _load_queued_song(self, song: dict) -> None:
        self.player.load_song(song)
        self._update_player_navigation()
        if song.get("video_id"):
            self.library.mark_played(song["video_id"])
            if (self.library_page.filter.currentIndex() == 2
                    or self.library_page.sort.currentIndex() >= 3):
                self.library_page.refresh()
            self.library_page.mark_playing(song["video_id"])
            self.home.refresh()
        self._refresh_up_next()
        self.toast_manager.show_toast("Now playing", song.get("title", "Selected track"), "info", 2600)

    def _update_player_navigation(self):
        self.player.set_navigation(
            bool(self.playback_queue.history),
            bool(self.playback_queue.upcoming)
            or (self.playback_queue.repeat == "all" and bool(self.playback_queue.context)),
        )

    def _play_previous(self):
        while self.playback_queue.history:
            video_id = self.playback_queue.previous()
            song = self.library.find(video_id) if video_id else None
            if song:
                self._load_queued_song(song)
                return
        self._refresh_up_next()

    def _play_next(self, automatic: bool = False):
        attempts = len(self.playback_queue.upcoming) + len(self.playback_queue.context) + 1
        for _ in range(attempts):
            video_id = self.playback_queue.next(automatic=automatic)
            if not video_id:
                self._update_player_navigation()
                self._refresh_up_next()
                return
            song = self.library.find(video_id)
            if song:
                self._load_queued_song(song)
                return

    def _on_media_status_changed(self, status) -> None:
        if status != QMediaPlayer.EndOfMedia or not self.playback_queue.current:
            return
        current = self.playback_queue.current
        QTimer.singleShot(0, lambda: self._advance_after_end(current))

    def _advance_after_end(self, video_id: str) -> None:
        if (self.playback_queue.current == video_id
                and self.player.player.mediaStatus() == QMediaPlayer.EndOfMedia):
            self._play_next(automatic=True)

    def _play_next_requested(self, video_id: str) -> None:
        song = self.library.find(video_id)
        if not song:
            return
        if not self.playback_queue.current:
            self._play_song(song)
            return
        self.playback_queue.play_next(video_id)
        self._refresh_up_next()
        self.toast_manager.show_toast("Added to Up Next", song["title"], "success")

    def _play_queued_index(self, index: int) -> None:
        video_id = self.playback_queue.play_at(index)
        song = self.library.find(video_id) if video_id else None
        if song:
            self._load_queued_song(song)
        else:
            self._play_next()

    def _remove_queued_index(self, index: int) -> None:
        if self.playback_queue.remove(index):
            self._refresh_up_next()

    def _clear_up_next(self) -> None:
        self.playback_queue.clear()
        self._refresh_up_next()

    def _reorder_up_next(self, video_ids: list[str]) -> None:
        if self.playback_queue.reorder(video_ids):
            self._update_player_navigation()

    def _toggle_shuffle(self) -> None:
        self.playback_queue.toggle_shuffle()
        self._refresh_up_next()

    def _cycle_repeat(self) -> None:
        self.playback_queue.cycle_repeat()
        self._refresh_up_next()

    def _refresh_up_next(self) -> None:
        self.up_next.set_queue(
            self.playback_queue.current, self.playback_queue.upcoming, self.library
        )
        self.player.set_playback_options(
            self.playback_queue.shuffle, self.playback_queue.repeat
        )
        self._update_player_navigation()

    def _on_track_changed(self, song):
        self.library_page.mark_playing(song.get("video_id", ""))
        QTimer.singleShot(0, self._sync_discord_presence)

    def _configure_discord(self, enabled: bool):
        self.discord_presence.configure(enabled)
        if enabled:
            self._on_playback_state_changed(self.player.player.playbackState())
        else:
            self._discord_refresh_timer.stop()
            self.discord_presence.clear()

    def _on_playback_state_changed(self, state) -> None:
        self._sync_discord_presence()
        if state == QMediaPlayer.PlayingState and self.settings.discord_config():
            self._discord_refresh_timer.start()
            QTimer.singleShot(1500, self._sync_discord_presence)
        else:
            self._discord_refresh_timer.stop()

    def _sync_discord_presence(self):
        enabled = self.settings.discord_config()
        if (
            enabled
            and self.player.current_song
            and self.player.player.playbackState() == QMediaPlayer.PlayingState
        ):
            song = dict(self.player.current_song)
            if not song.get("duration") and self.player.player.duration() > 0:
                song["duration"] = self.player.player.duration() // 1000
            self.discord_presence.show_song(
                song, self.player.player.position()
            )
        else:
            self.discord_presence.clear()

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
            if not self.download_state.enqueue(result):
                skipped += 1
                continue
            added.append(result)

        if not added:
            self.toast_manager.show_toast(
                "Nothing new to download",
                "Those tracks are already saved or already queued.",
                "warning",
            )
            return

        for result in added:
            playlist_id = getattr(result, "playlist_id", None)
            playlist = self._playlist_contexts.get(playlist_id)
            if playlist:
                self.download_state.remember_playlist(playlist)
        self.downloads.set_jobs(self.download_state.jobs)

        if was_idle:
            self._start_next_download(navigate_to_downloads=True)

        if batch:
            detail = f"{len(added)} tracks added to the queue"
            if skipped:
                detail += f" · {skipped} skipped"
            self.toast_manager.show_toast("Selection queued", detail, "info")
        elif not was_idle:
            self.toast_manager.show_toast(
                "Added to download queue",
                f"{result.title} · {len(self.download_state.jobs)} waiting",
                "info",
            )

    def _start_next_download(self, navigate_to_downloads: bool = False):
        if self._active_result or self._shutting_down:
            return
        job = self.download_state.next_queued()
        if not job:
            return
        self.download_state.set_status(job["video_id"], "active")
        self._active_result = result_from_job(job)
        result = self._active_result
        self.downloads.set_jobs(self.download_state.jobs)
        if navigate_to_downloads:
            self.navigate("downloading")
        self.toast_manager.show_toast("Download started", result.title, "info")
        if not self.downloader.download(result.video_id, result.title):
            self.toast_manager.show_toast(
                "Download could not start",
                "The download worker is still finishing its previous task.",
                "error",
            )
            self.download_state.set_status(result.video_id, "queued")
            self._active_result = None
            self.downloads.set_jobs(self.download_state.jobs)

    def _on_download_progress(self, value: int):
        if self._active_result:
            video_id = self._active_result.video_id
            self.download_state.set_progress(video_id, value)
            job = self.download_state.get(video_id)
            if job and job["status"] == "active":
                self.downloads.update_progress(video_id, value)
            elif job and video_id in self.downloads.rows:
                self.downloads.rows[video_id].update_job(job)

    def _on_download_transfer(self, percent: int, speed: int, eta: int) -> None:
        if self._active_result:
            self.downloads.update_transfer(
                self._active_result.video_id, percent, speed, eta
            )

    def _on_download_finished(self, file_path: str):
        result = self._active_result
        self._active_result = None
        if result:
            self.library.add_song(
                result.video_id, result.title, result.channel,
                result.thumbnail_url, file_path, result.duration,
            )
            self._update_downloaded_playlist(result)
            self.download_state.remove(result.video_id)
        self.library_page.refresh()
        self.home.refresh()
        self.downloads.set_jobs(self.download_state.jobs)
        self.toast_manager.show_toast(
            "Download complete",
            f"{result.title if result else 'track'} added to your library.",
            "success",
        )
        QTimer.singleShot(0, self._start_next_download)

    def _on_download_failed(self, message: str):
        result = self._active_result
        self._active_result = None
        reason = explain_download_error(message)
        if result:
            self.download_state.set_status(result.video_id, "failed", reason)
        self.downloads.set_jobs(self.download_state.jobs)
        self.toast_manager.show_toast(
            "Download failed",
            f"{result.title if result else 'track'} · {reason}",
            "error",
        )
        QTimer.singleShot(0, self._start_next_download)

    def _on_download_cancelled(self):
        result = self._active_result
        self._active_result = None
        if result and result.video_id in self._cancel_requested_ids:
            discard_download_files(result.video_id)
            self._cancel_requested_ids.discard(result.video_id)
        if result and not self._shutting_down:
            self.download_state.remove(result.video_id)
            self.downloads.set_jobs(self.download_state.jobs)
            QTimer.singleShot(0, self._start_next_download)

    def _on_download_action(self, action: str, video_id: str) -> None:
        job = self.download_state.get(video_id)
        if not job:
            return
        active = bool(
            self._active_result and self._active_result.video_id == video_id
        )
        if action == "pause" and job["status"] in ("active", "queued"):
            self.download_state.set_status(video_id, "paused")
            if active:
                self.downloader.pause()
        elif action == "resume" and job["status"] == "paused":
            if active:
                self.download_state.set_status(video_id, "active")
                self.downloader.resume()
            else:
                self.download_state.set_status(video_id, "queued")
                QTimer.singleShot(0, self._start_next_download)
        elif action == "retry" and job["status"] == "failed":
            self.download_state.set_status(video_id, "queued")
            QTimer.singleShot(0, self._start_next_download)
        elif action == "cancel":
            self.download_state.remove(video_id)
            if active:
                self._cancel_requested_ids.add(video_id)
                self.downloader.cancel()
            else:
                discard_download_files(video_id)
                QTimer.singleShot(0, self._start_next_download)
        self.downloads.set_jobs(self.download_state.jobs)

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
        self._shutting_down = True
        self.downloader.cancel()
        self.discord_presence.close()
        self.player.close()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "toast_manager"):
            self.toast_manager.setGeometry(self.centralWidget().rect())
