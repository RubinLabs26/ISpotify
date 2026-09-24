from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve, QPoint, QProcess, QPropertyAnimation, QTimer, QSize, Qt, QUrl,
    QVariantAnimation,
)
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
from ui.easter_eggs import (
    DISCO_COLORS, EasterEggs, TapWatcher, VolumeElevenWatcher,
)
from ui.home_tab import HomeTab
from ui.library_tab import LibraryTab
from ui.player_widget import PlayerWidget
from ui.search_tab import SearchTab
from ui.settings_tab import SettingsTab
from ui.theme import MOTION
from ui.toast import ToastManager
from ui.widgets import (
    MotionButton, SlidingIndicator, icon_button, standard_icon,
)

SIDEBAR_WIDTH = 200
BRAND_MARK_STYLE = "color: #f2f1ec; font-size: 10pt;"
DISCO_TICK_MS = 90
DISCO_TICKS = 12_000 // DISCO_TICK_MS


def _count(value: int, noun: str) -> str:
    return f"{value} {noun}{'' if value == 1 else 's'}"


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
        self._setup_easter_eggs()
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
        self.header.addLayout(title_box, 1)
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
        self._pages_fade.setDuration(MOTION["slow"])
        self._pages_fade.setEasingCurve(QEasingCurve.OutQuint)
        self._pages_opacity.setOpacity(1.0)
        # Incoming pages also rise a few pixels into place.
        self._page_slide = QPropertyAnimation(self)
        self._page_slide.setPropertyName(b"pos")
        self._page_slide.setDuration(MOTION["slow"])
        self._page_slide.setEasingCurve(QEasingCurve.OutCubic)
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
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 24, 20, 18)
        layout.setSpacing(4)
        brand_row = QHBoxLayout()
        brand_row.setSpacing(8)
        self.brand_mark = QLabel("●")
        self.brand_mark.setStyleSheet(BRAND_MARK_STYLE)
        self.brand_mark.setFixedWidth(14)
        self.brand_label = QLabel("iSpotify")
        self.brand_label.setObjectName("brand")
        brand_row.addWidget(self.brand_mark)
        brand_row.addWidget(self.brand_label)
        brand_row.addStretch()
        layout.addLayout(brand_row)
        layout.addSpacing(28)
        self.nav_indicator = SlidingIndicator(sidebar)
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
        self.library_page.libraryChanged.connect(self.home.refresh)
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
        self.player.player.mediaStatusChanged.connect(self._on_media_status_changed)
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

    # -- secrets ------------------------------------------------------------
    # Hidden on purpose; the full list lives in docs/EASTER_EGGS.md.

    def _setup_easter_eggs(self) -> None:
        self._zen = False
        self._zen_anim = QVariantAnimation(self)
        self._zen_anim.setDuration(MOTION["slow"])
        self._zen_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._zen_anim.valueChanged.connect(self._apply_sidebar_width)
        self._zen_anim.finished.connect(self._finish_zen_animation)
        self._disco_timer = QTimer(self)
        self._disco_timer.setInterval(DISCO_TICK_MS)
        self._disco_timer.timeout.connect(self._disco_tick)
        self._disco_ticks_left = 0
        self.easter_eggs = EasterEggs(self)
        self.easter_eggs.konamiEntered.connect(self._start_disco)
        self.easter_eggs.vinylToggled.connect(self._toggle_vinyl)
        self.easter_eggs.zenToggled.connect(lambda: self._set_zen(not self._zen))
        self.easter_eggs.escapePressed.connect(lambda: self._set_zen(False))
        self._vault_watcher = TapWatcher(
            (self.brand_mark, self.brand_label), taps=5, window=2.0, parent=self
        )
        self._vault_watcher.triggered.connect(self._open_vault)
        self._eleven_watcher = VolumeElevenWatcher(
            self.player.volume_slider, parent=self
        )
        self._eleven_watcher.triggered.connect(self._go_to_eleven)

    def _start_disco(self) -> None:
        self._disco_ticks_left = DISCO_TICKS
        if not self._disco_timer.isActive():
            self._disco_timer.start()
        self.toast_manager.show_toast(
            "Cheat code accepted", "Disco mode for twelve seconds. Dance responsibly.",
            "success",
        )

    def _disco_tick(self) -> None:
        self._disco_ticks_left -= 1
        if self._disco_ticks_left <= 0:
            self._stop_disco()
            return
        color = DISCO_COLORS[self._disco_ticks_left % len(DISCO_COLORS)]
        self.brand_mark.setStyleSheet(f"color: {color}; font-size: 10pt;")
        self.player.position_slider.setStyleSheet(
            f"QSlider::sub-page:horizontal {{ background: {color}; border-radius: 2px; }}"
        )

    def _stop_disco(self) -> None:
        self._disco_timer.stop()
        self._disco_ticks_left = 0
        self.brand_mark.setStyleSheet(BRAND_MARK_STYLE)
        self.player.position_slider.setStyleSheet("")

    def _toggle_vinyl(self) -> None:
        enabled = not self.player.vinyl_mode()
        self.player.set_vinyl_mode(enabled)
        if enabled:
            self.toast_manager.show_toast(
                "Vinyl mode", "Spinning at 33⅓ rpm. Type vinyl again to stop.", "success"
            )
        else:
            self.toast_manager.show_toast("Vinyl mode off", "Back to digital.", "info")

    def _set_zen(self, enabled: bool) -> None:
        if enabled == self._zen:
            return
        self._zen = enabled
        self._zen_anim.stop()
        start = self.sidebar.width() if self.sidebar.isVisible() else 0
        self.sidebar.show()
        self._zen_anim.setStartValue(start)
        self._zen_anim.setEndValue(0 if enabled else SIDEBAR_WIDTH)
        self._zen_anim.start()
        if enabled:
            self.toast_manager.show_toast(
                "Zen mode", "Just you and the music. Press Esc or type zen to return.",
                "info",
            )

    def _apply_sidebar_width(self, width) -> None:
        self.sidebar.setFixedWidth(max(0, int(width)))

    def _finish_zen_animation(self) -> None:
        if self._zen:
            self.sidebar.hide()
        else:
            self.sidebar.setFixedWidth(SIDEBAR_WIDTH)

    def _open_vault(self) -> None:
        songs = self.library.all_songs()
        plays = sum(int(song.get("play_count") or 0) for song in songs)
        stats = [
            _count(len(songs), "song"),
            _count(len(self.library.favorites()), "favorite"),
            _count(len(self.library.all_playlists()), "playlist"),
            _count(plays, "play"),
        ]
        self.toast_manager.show_toast(
            "You found the vault",
            " · ".join(stats) + f"\niSpotify v{APP_VERSION}, made with care by Rubin Labs.",
            "success", timeout=6500,
        )

    def _go_to_eleven(self) -> None:
        self.toast_manager.show_toast(
            "This one goes to eleven",
            "It's one louder. Your speakers are grateful we stopped at 100.",
            "info",
        )

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
            self._pages_fade.setStartValue(0.35)
            self._pages_fade.setEndValue(1.0)
            self._pages_fade.start()
            self._slide_in(widget)
        self.page_title.setText(title)
        self.page_subtitle.setText(subtitle)
        for key, button in self._nav_buttons:
            button.setChecked(key == page)
            if key == page:
                self.nav_indicator.track(button)
        self._current_page = page
        self._update_back_button()

    def _slide_in(self, widget) -> None:
        previous = self._page_slide.targetObject()
        self._page_slide.stop()
        rest = self.pages.contentsRect().topLeft()
        if previous is not None and previous is not widget:
            previous.move(rest)
        if not self.isVisible():
            widget.move(rest)
            return
        self._page_slide.setTargetObject(widget)
        self._page_slide.setStartValue(rest + QPoint(0, 14))
        self._page_slide.setEndValue(rest)
        self._page_slide.start()

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
        self.toast_manager.show_toast("Now playing", song.get("title", "Selected track"), "info", 2600)

    def _update_player_navigation(self):
        self.player.set_navigation(
            bool(self.playback_queue.history),
            bool(self.playback_queue.upcoming),
        )

    def _play_previous(self):
        while self.playback_queue.history:
            video_id = self.playback_queue.previous()
            song = self.library.find(video_id) if video_id else None
            if song:
                self._load_queued_song(song)
                return
        self._update_player_navigation()

    def _play_next(self):
        attempts = len(self.playback_queue.upcoming)
        for _ in range(attempts):
            video_id = self.playback_queue.next()
            if not video_id:
                self._update_player_navigation()
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
            self._play_next()

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
        self._disco_timer.stop()
        self.downloader.cancel()
        self.discord_presence.close()
        self.player.close()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "toast_manager"):
            self.toast_manager.setGeometry(self.centralWidget().rect())
