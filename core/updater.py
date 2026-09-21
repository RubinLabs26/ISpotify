"""Asynchronous GitHub release checks and verified update downloads."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from core.paths import CACHE_DIR
from core.version import APP_VERSION


RELEASE_API = "https://api.github.com/repos/RubinLabs26/ISpotify/releases/latest"
RELEASE_PAGE = "https://github.com/RubinLabs26/ISpotify/releases/latest"
VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def version_tuple(value: str) -> tuple[int, int, int] | None:
    match = VERSION_PATTERN.fullmatch(str(value or ""))
    return tuple(map(int, match.groups())) if match else None


def is_newer(candidate: str, current: str = APP_VERSION) -> bool:
    found = version_tuple(candidate)
    installed = version_tuple(current)
    return bool(found and installed and found > installed)


def update_asset_name() -> str | None:
    if sys.platform == "win32":
        installed = (
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Programs" / "ISpotify" / "ISpotify.exe"
        )
        executable = Path(sys.executable)
        if (
            getattr(sys, "frozen", False)
            and executable.resolve() != installed.resolve()
            and os.access(executable.parent, os.W_OK)
        ):
            return "ISpotify-windows-x86_64.exe"
        return "ISpotify-Setup-x86_64.exe"
    if sys.platform.startswith("linux"):
        if Path("/var/lib/dpkg/info/ispotify.list").is_file():
            return f"ispotify_{{version}}_amd64.deb"
        if getattr(sys, "frozen", False):
            return "ISpotify-linux-x86_64"
    return None


def release_asset(release: dict, asset_name: str) -> dict | None:
    for asset in release.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        if asset.get("name") != asset_name:
            continue
        digest = str(asset.get("digest") or "")
        url = str(asset.get("browser_download_url") or "")
        if re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest) and url.startswith(
            "https://github.com/RubinLabs26/ISpotify/releases/download/"
        ):
            return asset
    return None


class UpdateManager(QObject):
    checkStarted = Signal()
    updateAvailable = Signal(str)
    upToDate = Signal()
    failed = Signal(str)
    downloadProgress = Signal(int, int)
    downloadReady = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._network = QNetworkAccessManager(self)
        self._check_reply = None
        self._download_reply = None
        self._download_file = None
        self._hash = None
        self._expected_hash = ""
        self._download_path: Path | None = None
        self.release: dict | None = None
        self.asset: dict | None = None

    @staticmethod
    def _request(url: str, timeout_ms: int = 15_000) -> QNetworkRequest:
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", b"iSpotify-Updater")
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setAttribute(
            QNetworkRequest.RedirectPolicyAttribute,
            QNetworkRequest.NoLessSafeRedirectPolicy,
        )
        request.setTransferTimeout(timeout_ms)
        return request

    def check(self) -> None:
        if self._check_reply or self._download_reply:
            return
        self.checkStarted.emit()
        reply = self._network.get(self._request(RELEASE_API))
        self._check_reply = reply
        reply.finished.connect(lambda: self._finish_check(reply))

    def _finish_check(self, reply: QNetworkReply) -> None:
        self._check_reply = None
        try:
            if reply.error() != QNetworkReply.NoError:
                self.failed.emit(f"Update check failed: {reply.errorString()}")
                return
            release = json.loads(bytes(reply.readAll()))
            if not isinstance(release, dict) or not version_tuple(
                release.get("tag_name", "")
            ):
                self.failed.emit("Update check returned invalid release data.")
                return
            self.release = release
            version = release["tag_name"].lstrip("v")
            name = update_asset_name()
            self.asset = release_asset(
                release, name.format(version=version)
            ) if name else None
            if is_newer(version):
                self.updateAvailable.emit(version)
            else:
                self.upToDate.emit()
        except (ValueError, TypeError, KeyError) as exc:
            self.failed.emit(f"Update check failed: {exc}")
        finally:
            reply.deleteLater()

    def download(self) -> None:
        if self._download_reply or not self.release or not self.asset:
            return
        version = str(self.release["tag_name"]).lstrip("v")
        folder = CACHE_DIR / "updates" / version
        folder.mkdir(parents=True, exist_ok=True)
        self._download_path = folder / str(self.asset["name"])
        partial = self._download_path.with_name(self._download_path.name + ".part")
        self._expected_hash = str(self.asset["digest"]).split(":", 1)[1].lower()
        if self._download_path.is_file() and self._file_hash(self._download_path) == self._expected_hash:
            self.downloadReady.emit(str(self._download_path))
            return
        self._hash = hashlib.sha256()
        try:
            self._download_file = partial.open("wb")
        except OSError as exc:
            self.failed.emit(f"Could not save update: {exc}")
            return
        reply = self._network.get(
            self._request(self.asset["browser_download_url"], 60_000)
        )
        self._download_reply = reply
        reply.readyRead.connect(lambda: self._read_chunk(reply))
        reply.downloadProgress.connect(self.downloadProgress.emit)
        reply.finished.connect(lambda: self._finish_download(reply, partial))

    def _read_chunk(self, reply: QNetworkReply) -> None:
        if self._download_file is None:
            return
        chunk = bytes(reply.readAll())
        if chunk:
            self._download_file.write(chunk)
            self._hash.update(chunk)

    def _finish_download(self, reply: QNetworkReply, partial: Path) -> None:
        self._download_reply = None
        try:
            self._read_chunk(reply)
            self._download_file.close()
            self._download_file = None
            if reply.error() != QNetworkReply.NoError:
                raise OSError(reply.errorString())
            if self._hash.hexdigest() != self._expected_hash:
                raise ValueError("SHA-256 verification failed")
            os.replace(partial, self._download_path)
            self.downloadReady.emit(str(self._download_path))
        except (OSError, ValueError) as exc:
            partial.unlink(missing_ok=True)
            self.failed.emit(f"Update download failed: {exc}")
        finally:
            reply.deleteLater()

    @staticmethod
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
