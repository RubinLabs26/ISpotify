"""Discord Rich Presence over the locally signed-in desktop client."""

from __future__ import annotations

import os
import queue
import threading
import time
from typing import Any

from PySide6.QtCore import QObject, Signal

try:
    from pypresence import ActivityType, Presence
    LISTENING_ACTIVITY = ActivityType.LISTENING
except ImportError:  # Keeps source checkouts usable until dependencies install.
    Presence = None
    LISTENING_ACTIVITY = 2


DEFAULT_APPLICATION_ID = os.environ.get(
    "ISPOTIFY_DISCORD_APPLICATION_ID", ""
).strip()


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
    """Run Discord IPC away from Qt's UI thread and reconnect quietly."""

    statusChanged = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._commands: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._thread: threading.Thread | None = None

    def configure(self, application_id: str, enabled: bool) -> None:
        self._ensure_thread()
        self._commands.put(("configure", (application_id.strip(), enabled)))

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
        thread.join(timeout=2)
        self._thread = None

    def _ensure_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run, name="discord-presence", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        rpc = None
        application_id = ""
        enabled = False
        latest_activity = None

        def dispose_failed_connection(candidate) -> None:
            """Close transports left behind when the Discord handshake fails."""
            writer = getattr(candidate, "sock_writer", None)
            loop = getattr(candidate, "loop", None)
            if writer is not None:
                try:
                    writer.close()
                    if (
                        loop is not None
                        and not loop.is_closed()
                        and hasattr(writer, "wait_closed")
                    ):
                        loop.run_until_complete(writer.wait_closed())
                except Exception:
                    pass
                # pypresence exposes the raw Windows pipe transport. Finish
                # its deferred close before closing the private event loop.
                if hasattr(writer, "_call_connection_lost"):
                    try:
                        writer._call_connection_lost(None)
                    except Exception:
                        sock = getattr(writer, "_sock", None)
                        if sock is not None:
                            try:
                                sock.close()
                            except Exception:
                                pass
                        writer._sock = None
            if loop is not None and not loop.is_closed():
                try:
                    loop.close()
                except Exception:
                    pass

        def disconnect() -> None:
            nonlocal rpc
            if rpc is None:
                return
            try:
                rpc.clear()
            except Exception:
                pass
            try:
                rpc.close()
            except Exception:
                pass
            rpc = None

        def connect() -> bool:
            nonlocal rpc
            if not enabled or not valid_application_id(application_id):
                return False
            if Presence is None:
                self.statusChanged.emit(False, "Discord support is not installed")
                return False
            if rpc is not None:
                return True
            candidate = None
            try:
                candidate = Presence(application_id)
                candidate.connect()
            except Exception:
                if candidate is not None:
                    dispose_failed_connection(candidate)
                rpc = None
                self.statusChanged.emit(
                    False, "Open and sign in to the Discord desktop app"
                )
                return False
            rpc = candidate
            self.statusChanged.emit(True, "Connected to Discord")
            return True

        while True:
            try:
                command, value = self._commands.get(timeout=15)
            except queue.Empty:
                if rpc is None and latest_activity is not None and connect():
                    try:
                        rpc.update(**latest_activity)
                    except Exception:
                        disconnect()
                continue

            if command == "stop":
                disconnect()
                return
            if command == "configure":
                new_id, new_enabled = value
                if new_id != application_id or not new_enabled:
                    disconnect()
                application_id = new_id
                enabled = bool(new_enabled and valid_application_id(new_id))
                if not enabled:
                    latest_activity = None
                    self.statusChanged.emit(False, "Discord activity is off")
                else:
                    connect()
                continue
            if command == "clear":
                latest_activity = None
                if rpc is not None:
                    try:
                        rpc.clear()
                    except Exception:
                        disconnect()
                continue
            if command == "update":
                latest_activity = value
                if connect():
                    try:
                        rpc.update(**latest_activity)
                        self.statusChanged.emit(True, "Showing listening activity")
                    except Exception:
                        disconnect()
                        self.statusChanged.emit(
                            False, "Discord disconnected; reconnecting soon"
                        )
