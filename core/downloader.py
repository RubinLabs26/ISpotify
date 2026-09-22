"""Managed background yt-dlp audio downloader.

Each job runs through Qt's shared thread pool.  This keeps failed batch items
from racing QThread deletion while the next queued item is starting.
"""

import shutil
import threading
import re
import math

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from core.cookies import ydl_cookie_kwargs, ydl_youtube_compat_kwargs
from core.paths import DOWNLOAD_DIR, ensure_directories


def explain_download_error(message: str) -> str:
    """Turn common yt-dlp failures into useful next steps."""
    detail = str(message or "").strip()
    lower = detail.lower()
    if any(text in lower for text in ("not a bot", "sign in to confirm", "captcha", "cookies")):
        return "YouTube needs verification. Update cookies in Settings, then Retry."
    if "403" in lower or "forbidden" in lower:
        return "The source denied this download. Check cookies in Settings, then Retry."
    if "unavailable" in lower or "private video" in lower:
        return "This track is unavailable. Try another search result."
    if any(text in lower for text in ("timed out", "connection", "network", "http error 5")):
        return "The connection failed. Check your network, then Retry."
    if "ffmpeg" in lower or "postprocessing" in lower:
        return "Audio conversion failed. Check FFmpeg, then Retry."
    if "no space left" in lower or "disk full" in lower:
        return "Not enough disk space. Free space, then Retry."
    return detail[:300] or "The download failed. Try again."


def _positive_int(value) -> int:
    try:
        number = float(value)
        return max(0, int(number)) if math.isfinite(number) else 0
    except (TypeError, ValueError, OverflowError):
        return 0


def discard_download_files(video_id: str) -> None:
    """Remove files owned by a cancelled job from the app download folder."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
        return
    for path in DOWNLOAD_DIR.glob(f"{video_id}.*"):
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                pass


class _QuietYdlLogger:
    """Keep handled yt-dlp retries out of the terminal."""

    def debug(self, _message):
        pass

    def warning(self, _message):
        pass

    def error(self, _message):
        pass


def ffmpeg_location() -> str | None:
    """Use system FFmpeg, with imageio-ffmpeg as a portable fallback."""
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError, OSError):
        return None


class DownloadSignals(QObject):
    progress = Signal(int)
    transfer = Signal(int, int, int)
    finished = Signal(str)
    error = Signal(str)
    cancelled = Signal()


class DownloadCancelled(Exception):
    """Control-flow signal raised from a yt-dlp progress callback."""


class DownloadTask(QRunnable):
    def __init__(self, video_id: str, title: str):
        super().__init__()
        self.video_id = video_id
        self.title = title
        self.signals = DownloadSignals()
        self._paused = threading.Event()
        self._cancelled = threading.Event()
        self.setAutoDelete(False)

    def run(self):
        try:
            result = self._download()
            if self._cancelled.is_set():
                self.signals.cancelled.emit()
            else:
                self.signals.finished.emit(result)
        except Exception as exc:
            if self._cancelled.is_set() or isinstance(exc, DownloadCancelled):
                self.signals.cancelled.emit()
            else:
                self.signals.error.emit(str(exc))

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def cancel(self) -> None:
        self._cancelled.set()
        self._paused.clear()

    def _wait_for_control(self) -> None:
        while self._paused.is_set() and not self._cancelled.is_set():
            self._cancelled.wait(0.1)
        if self._cancelled.is_set():
            raise DownloadCancelled()

    def _progress_hook(self, data):
        self._wait_for_control()
        if data.get("status") == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes", 0)
            percent = min(100, int(downloaded / total * 100)) if total else 0
            self.signals.progress.emit(percent)
            self.signals.transfer.emit(
                percent, _positive_int(data.get("speed")),
                _positive_int(data.get("eta")),
            )
        elif data.get("status") == "finished":
            self.signals.progress.emit(100)

    def _download(self) -> str:
        import yt_dlp

        ensure_directories()
        options = {
            "format": "bestaudio/best",
            "outtmpl": str(DOWNLOAD_DIR / "%(id)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "progress_hooks": [self._progress_hook],
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "retries": 2,
            "socket_timeout": 15,
            "continuedl": True,
            "nopart": False,
            "logger": _QuietYdlLogger(),
        }
        converter = ffmpeg_location()
        if converter:
            options["ffmpeg_location"] = converter
        options.update(ydl_youtube_compat_kwargs())
        cookie_options = ydl_cookie_kwargs()
        options.update(cookie_options)
        url = f"https://www.youtube.com/watch?v={self.video_id}"
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as exc:
            message = str(exc)
            if cookie_options and "page needs to be reloaded" in message.lower():
                # The logged-in YouTube player is currently unreliable even
                # with valid cookies. Public tracks often work immediately as
                # a guest, so retry the same download without authentication.
                guest_options = dict(options)
                guest_options.pop("cookiefile", None)
                try:
                    with yt_dlp.YoutubeDL(guest_options) as ydl:
                        ydl.download([url])
                except yt_dlp.utils.DownloadError as guest_exc:
                    raise RuntimeError(
                        "YouTube rejected both its signed-in and public player "
                        f"paths: {guest_exc}"
                    ) from guest_exc
            else:
                if any(
                    marker in message
                    for marker in ("Sign in to confirm", "not a bot", "cookies")
                ):
                    raise RuntimeError(
                        "YouTube is asking for sign-in verification. Add your "
                        "browser cookies in Settings and try again."
                    ) from exc
                raise

        final_path = DOWNLOAD_DIR / f"{self.video_id}.mp3"
        if not final_path.exists():
            raise FileNotFoundError("The converted audio file was not created.")
        return str(final_path)


class Downloader(QObject):
    progress = Signal(int)
    transfer = Signal(int, int, int)
    downloadFinished = Signal(str)
    downloadFailed = Signal(str)
    downloadCancelled = Signal()

    def __init__(self):
        super().__init__()
        self._pool = QThreadPool.globalInstance()
        self._task = None
        self._active = False

    def download(self, video_id: str, title: str):
        if self._active:
            return False

        self._active = True
        task = DownloadTask(video_id, title)
        self._task = task
        task.signals.progress.connect(self.progress.emit)
        task.signals.transfer.connect(self.transfer.emit)
        task.signals.finished.connect(self._on_finished)
        task.signals.error.connect(self._on_error)
        task.signals.cancelled.connect(self._on_cancelled)
        self._pool.start(task)
        return True

    def _on_finished(self, file_path: str):
        self._finish_task()
        self.downloadFinished.emit(file_path)

    def _on_error(self, message: str):
        self._finish_task()
        self.downloadFailed.emit(message or "The download did not complete.")

    def _on_cancelled(self):
        self._finish_task()
        self.downloadCancelled.emit()

    def pause(self) -> None:
        if self._task is not None:
            self._task.pause()

    def resume(self) -> None:
        if self._task is not None:
            self._task.resume()

    def cancel(self) -> None:
        if self._task is not None:
            self._task.cancel()

    def _finish_task(self):
        self._active = False
        task = self._task
        self._task = None
        if task is not None:
            task.signals.deleteLater()
