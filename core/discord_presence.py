"""Discord listening activity with optional browser-based account login."""

from __future__ import annotations

import queue
import threading
import time
from typing import Any

from PySide6.QtCore import QObject, Signal

from core.discord_social_sdk import (
    APPLICATION_ID,
    DiscordSdkError,
    DiscordSocialClient,
    TokenStore,
)


DEFAULT_APPLICATION_ID = str(APPLICATION_ID)
LISTENING_ACTIVITY = 2


def valid_application_id(value: str | None) -> bool:
    """Discord application IDs are public numeric snowflakes, never tokens."""
    text = (value or "").strip()
    return text.isascii() and text.isdigit() and 17 <= len(text) <= 20


def presence_payload(song: dict[str, Any], position_ms: int = 0) -> dict[str, Any]:
    """Create a bounded Discord activity for the current song."""
    title = " ".join(str(song.get("title") or "Unknown track").split())[:128]
    artist = " ".join(str(song.get("channel") or "Unknown artist").split())[:128]
    payload: dict[str, Any] = {
        "activity_type": LISTENING_ACTIVITY,
        "details": title or "Unknown track",
        "state": artist or "Unknown artist",
    }
    if position_ms > 0:
        payload["start"] = max(0, int(time.time() - position_ms / 1000))
    return payload


class DiscordPresence(QObject):
    """Run Discord SDK authorization and presence outside Qt's UI thread."""

    statusChanged = Signal(bool, str)
    accountChanged = Signal(bool, str)
    authorizationUrlReady = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._commands: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._thread: threading.Thread | None = None

    def configure(self, enabled: bool) -> None:
        self._ensure_thread()
        self._commands.put(("configure", bool(enabled)))

    def login(self) -> None:
        self._ensure_thread()
        self._commands.put(("login", None))

    def logout(self) -> None:
        self._ensure_thread()
        self._commands.put(("logout", None))

    def show_song(self, song: dict[str, Any], position_ms: int = 0) -> None:
        self._ensure_thread()
        self._commands.put(("update", presence_payload(song, position_ms)))

    def clear(self) -> None:
        if self._thread is not None:
            self._commands.put(("clear", None))

    def close(self) -> None:
        thread = self._thread
        if thread is None:
            return
        self._commands.put(("stop", None))
        thread.join(timeout=4)
        self._thread = None

    def _ensure_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run, name="discord-presence", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        enabled = False
        latest_activity = None
        client: DiscordSocialClient | None = None
        token_store = TokenStore()
        credentials_loaded = False

        def tokens_received(access: str, refresh: str, expires_in: int) -> None:
            if not token_store.save(access, refresh, expires_in):
                self.statusChanged.emit(
                    False,
                    "Connected for this session; credential storage is unavailable",
                )

        def account_changed(connected: bool, text: str) -> None:
            if not connected and "failed" in text.lower():
                token_store.clear()
            self.accountChanged.emit(connected, text)

        def sdk_status(status: int, error: int) -> None:
            if status == DiscordSocialClient.READY:
                self.statusChanged.emit(True, "Connected to Discord")
                if enabled and latest_activity is not None and client is not None:
                    client.update_presence(latest_activity)
            elif error:
                self.statusChanged.emit(False, "Discord connection was interrupted")

        def get_client() -> DiscordSocialClient | None:
            nonlocal client, credentials_loaded
            if client is not None:
                return client
            try:
                client = DiscordSocialClient(
                    sdk_status,
                    tokens_received,
                    account_changed,
                    self.authorizationUrlReady.emit,
                )
            except (DiscordSdkError, OSError) as exc:
                self.statusChanged.emit(False, str(exc))
                return None
            if not credentials_loaded:
                credentials_loaded = True
                credentials = token_store.load()
                if credentials:
                    self.accountChanged.emit(False, "Restoring Discord login…")
                    client.restore(credentials)
                else:
                    self.accountChanged.emit(False, "Not connected")
            return client

        while True:
            try:
                command, value = self._commands.get(timeout=0.05)
            except queue.Empty:
                if client is not None:
                    client.run_callbacks()
                continue

            if command == "stop":
                if client is not None:
                    client.close()
                return
            if command == "configure":
                enabled = bool(value)
                if enabled:
                    if get_client() is not None:
                        self.statusChanged.emit(False, "Discord activity is ready")
                else:
                    latest_activity = None
                    if client is not None:
                        client.clear_presence()
                    self.statusChanged.emit(False, "Discord activity is off")
            elif command == "login":
                sdk = get_client()
                if sdk is not None:
                    self.accountChanged.emit(False, "Waiting for Discord authorization…")
                    sdk.login()
                else:
                    self.accountChanged.emit(False, "Discord login is unavailable")
            elif command == "logout":
                token_store.clear()
                if client is not None:
                    client.logout()
                else:
                    self.accountChanged.emit(False, "Not connected")
            elif command == "clear":
                latest_activity = None
                if client is not None:
                    client.clear_presence()
            elif command == "update":
                latest_activity = value
                if enabled:
                    sdk = get_client()
                    if sdk is not None:
                        sdk.update_presence(latest_activity)
                        self.statusChanged.emit(True, "Showing listening activity")

            if client is not None:
                client.run_callbacks()
