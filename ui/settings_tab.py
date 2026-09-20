from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QTextEdit, QVBoxLayout, QWidget,
)

from core import cookies
from ui.widgets import MotionButton, StatusDot

COOKIE_PLACEHOLDER = "Paste your exported cookies here (JSON array, or a cookies.txt)…"

COOKIE_EXAMPLE = (
    '[{"domain": ".youtube.com", "name": "SID", "value": "…", '
    '"path": "/", "secure": true, "expirationDate": 1789830841}, …]'
)


class CookieValidationWorker(QObject):
    succeeded = Signal(int, str)
    failed = Signal(str)

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    @Slot()
    def run(self):
        try:
            count, warning = cookies.validate_and_save_cookies(self.text)
        except cookies.CookieError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Cookie validation failed unexpectedly: {exc}")
        else:
            self.succeeded.emit(count, warning)


class SettingsTab(QWidget):
    statusChanged = Signal(str)
    discordChanged = Signal(bool)
    discordLoginRequested = Signal()
    discordLogoutRequested = Signal()

    def __init__(self):
        super().__init__()
        self._validation_thread = None
        self._validation_worker = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 0, 8, 24)
        root.setSpacing(18)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._settings = QSettings("Rubin Labs", "iSpotify")
        discord_card = QFrame()
        discord_card.setObjectName("card")
        discord_layout = QVBoxLayout(discord_card)
        discord_layout.setContentsMargins(20, 16, 20, 16)
        discord_layout.setSpacing(7)
        discord_header = QHBoxLayout()
        discord_title = QLabel("Discord Rich Presence")
        discord_title.setObjectName("sectionTitle")
        discord_header.addWidget(discord_title)
        discord_header.addStretch()
        self.discord_toggle = QCheckBox("Show listening activity")
        discord_header.addWidget(self.discord_toggle)
        discord_layout.addLayout(discord_header)
        discord_detail = QLabel(
            "Displays Listening to iSpotify and the current track. Connect your "
            "Discord account in a browser, or use the signed-in desktop app."
        )
        discord_detail.setObjectName("secondary")
        discord_detail.setWordWrap(True)
        discord_layout.addWidget(discord_detail)
        discord_config = QHBoxLayout()
        self.discord_account = QLabel("Not connected")
        self.discord_account.setObjectName("secondary")
        discord_config.addWidget(self.discord_account)
        discord_config.addStretch()
        self.discord_account_button = MotionButton("Connect Discord account")
        self.discord_account_button.setObjectName("ghostButton")
        self.discord_account_button.clicked.connect(self._on_discord_account)
        discord_config.addWidget(self.discord_account_button)
        discord_layout.addLayout(discord_config)
        self.discord_status = QLabel("Discord activity is off")
        self.discord_status.setObjectName("muted")
        discord_layout.addWidget(self.discord_status)
        root.addWidget(discord_card)

        self.discord_toggle.setChecked(
            self._settings.value("discord/enabled", False, type=bool)
        )
        self.discord_toggle.toggled.connect(self._save_discord_settings)
        self._discord_connected = False
        self._settings.remove("discord/application_id")

        intro = QFrame()
        intro.setObjectName("card")
        intro_layout = QVBoxLayout(intro)
        intro_layout.setContentsMargins(20, 18, 20, 18)
        intro_layout.setSpacing(6)
        title = QLabel("YouTube cookies")
        title.setObjectName("sectionTitle")
        title.setStyleSheet("font-size: 12pt;")
        detail = QLabel(
            "If search or downloads start failing with a sign-in or bot-check "
            "error, YouTube is asking for proof you're a real browser. Paste "
            "cookies exported from a browser where you're logged into YouTube "
            "and iSpotify will send them the same way your browser does."
        )
        detail.setObjectName("secondary")
        detail.setWordWrap(True)
        intro_layout.addWidget(title)
        intro_layout.addWidget(detail)
        root.addWidget(intro)

        steps = QFrame()
        steps.setObjectName("card")
        steps_layout = QVBoxLayout(steps)
        steps_layout.setContentsMargins(20, 16, 20, 16)
        steps_layout.setSpacing(4)
        steps_title = QLabel("How to get them")
        steps_title.setObjectName("eyebrow")
        steps_layout.addWidget(steps_title)
        for line in (
            "1.  Open one private/incognito window and sign in to YouTube.",
            "2.  In that same tab, open youtube.com/robots.txt.",
            "3.  Export youtube.com cookies as JSON or cookies.txt, then close that window.",
            "4.  Paste the complete export below and choose Test & save cookies.",
        ):
            step_label = QLabel(line)
            step_label.setObjectName("secondary")
            step_label.setWordWrap(True)
            steps_layout.addWidget(step_label)
        root.addWidget(steps)

        example = QLabel(COOKIE_EXAMPLE)
        example.setObjectName("muted")
        example.setWordWrap(True)
        example.setStyleSheet(
            'font-family: "DejaVu Sans Mono", "Consolas", monospace; '
            "font-size: 8pt; padding: 2px 2px 0 2px;"
        )
        root.addWidget(example)

        self.cookie_box = QTextEdit()
        self.cookie_box.setObjectName("cookieBox")
        self.cookie_box.setPlaceholderText(COOKIE_PLACEHOLDER)
        self.cookie_box.setMinimumHeight(220)
        self.cookie_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.cookie_box.setPlainText(cookies.load_saved_text())
        root.addWidget(self.cookie_box, 1)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.status_dot = StatusDot(
            cookies.is_configured(), cookies.status_text(), "No cookies saved yet"
        )
        actions.addWidget(self.status_dot)
        self.status_label = QLabel(cookies.status_text())
        self.status_label.setObjectName("muted")
        actions.addWidget(self.status_label)
        actions.addStretch()
        self.clear_button = MotionButton("Clear")
        self.clear_button.setObjectName("ghostButton")
        self.clear_button.clicked.connect(self._on_clear)
        actions.addWidget(self.clear_button)
        self.save_button = MotionButton("Test & save cookies")
        self.save_button.setObjectName("accentButton")
        self.save_button.clicked.connect(self._on_save)
        actions.addWidget(self.save_button)
        root.addLayout(actions)

        privacy = QLabel(
            "Stored only on this computer, never uploaded anywhere except "
            "youtube.com by the app itself."
        )
        privacy.setObjectName("muted")
        privacy.setStyleSheet("font-size: 8pt;")
        privacy.setWordWrap(True)
        root.addWidget(privacy)

    def discord_config(self) -> bool:
        return self.discord_toggle.isChecked()

    def set_discord_status(self, connected: bool, text: str) -> None:
        self.discord_status.setText(text)
        self.discord_status.setStyleSheet(
            "color: #9c9c9f;" if connected else "color: #7d7d81;"
        )

    def set_discord_account(self, connected: bool, text: str) -> None:
        self._discord_connected = connected
        self.discord_account.setText(
            f"Connected as {text}" if connected else text
        )
        self.discord_account_button.setText(
            "Disconnect" if connected else "Connect Discord account"
        )
        self.discord_account_button.setEnabled(
            "waiting" not in text.lower() and "restoring" not in text.lower()
        )

    def _on_discord_account(self) -> None:
        self.discord_account_button.setEnabled(False)
        if self._discord_connected:
            self.discordLogoutRequested.emit()
        else:
            self.discordLoginRequested.emit()

    def _save_discord_settings(self) -> None:
        enabled = self.discord_config()
        self._settings.setValue("discord/enabled", enabled)
        self.discordChanged.emit(enabled)

    def _refresh_status(self):
        configured = cookies.is_configured()
        text = cookies.status_text()
        self.status_dot.set_state(configured, text, "No cookies saved yet")
        self.status_label.setText(text)

    def _on_save(self):
        text = self.cookie_box.toPlainText()
        if self._validation_thread is not None:
            return
        try:
            cookies.validate_cookie_text(text)
        except cookies.CookieError as exc:
            self.statusChanged.emit(f"error::{exc}")
            return
        self._set_testing(True)
        self.status_label.setText("Testing sign-in and download access…")
        thread = QThread(self)
        worker = CookieValidationWorker(text)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._validation_succeeded)
        worker.failed.connect(self._validation_failed)
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._validation_finished)
        self._validation_thread = thread
        self._validation_worker = worker
        thread.start()

    def _set_testing(self, testing: bool):
        self.cookie_box.setEnabled(not testing)
        self.clear_button.setEnabled(not testing)
        self.save_button.setEnabled(not testing)
        self.save_button.setText("Testing…" if testing else "Test & save cookies")

    @Slot(int, str)
    def _validation_succeeded(self, count: int, warning: str):
        self._refresh_status()
        if warning:
            self.statusChanged.emit(
                f"warning::Verified and saved {count} cookies. {warning}"
            )
        else:
            self.statusChanged.emit(
                f"success::Verified and saved {count} cookies. Downloads are ready."
            )

    @Slot(str)
    def _validation_failed(self, message: str):
        self._refresh_status()
        self.statusChanged.emit(f"error::{message}")

    @Slot()
    def _validation_finished(self):
        self._validation_thread = None
        self._validation_worker = None
        self._set_testing(False)

    def _on_clear(self):
        cookies.clear_cookies()
        self.cookie_box.clear()
        self._refresh_status()
        self.statusChanged.emit("info::Cookies cleared.")
