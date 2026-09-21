"""Durable download queue and playlist context for interrupted sessions."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from core.paths import DATA_DIR
from core.searcher import PlaylistResult, PlaylistTrack, SearchResult


QUEUE_FILE = DATA_DIR / "download_queue.json"
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
STATES = {"queued", "active", "paused", "failed"}


def _track_data(track) -> dict:
    return {
        "video_id": str(getattr(track, "video_id", "") or ""),
        "title": str(getattr(track, "title", "Unknown title") or "Unknown title"),
        "channel": str(getattr(track, "channel", "") or ""),
        "thumbnail_url": str(getattr(track, "thumbnail_url", "") or ""),
        "duration": int(getattr(track, "duration", 0) or 0),
    }


def result_from_job(job: dict) -> SearchResult:
    values = (
        job["video_id"], job["title"], job["channel"],
        job["thumbnail_url"], job["duration"],
    )
    if job.get("playlist_id"):
        return PlaylistTrack(*values, playlist_id=job["playlist_id"])
    return SearchResult(*values)


class DownloadState:
    def __init__(self, path: Path = QUEUE_FILE):
        self.path = path
        self.jobs: list[dict] = []
        self.playlists: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                return
            for raw in document.get("jobs", []):
                if not isinstance(raw, dict):
                    continue
                video_id = str(raw.get("video_id") or "")
                if not VIDEO_ID.fullmatch(video_id):
                    continue
                status = raw.get("status")
                if status not in STATES:
                    continue
                job = {
                    "video_id": video_id,
                    "title": str(raw.get("title") or "Unknown title"),
                    "channel": str(raw.get("channel") or ""),
                    "thumbnail_url": str(raw.get("thumbnail_url") or ""),
                    "duration": max(0, int(raw.get("duration") or 0)),
                    "playlist_id": str(raw.get("playlist_id") or ""),
                    "status": "queued" if status == "active" else status,
                    "progress": max(0, min(100, int(raw.get("progress") or 0))),
                    "error": str(raw.get("error") or ""),
                }
                if not self.get(video_id):
                    self.jobs.append(job)
            playlists = document.get("playlists") or {}
            if isinstance(playlists, dict):
                self.playlists = {
                    key: value for key, value in playlists.items()
                    if isinstance(key, str) and isinstance(value, dict)
                }
        except (OSError, ValueError, TypeError):
            self.jobs = []
            self.playlists = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(
            prefix="download-queue-", suffix=".json", dir=self.path.parent
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(
                    {"version": 1, "jobs": self.jobs, "playlists": self.playlists},
                    stream, ensure_ascii=False, indent=2,
                )
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def get(self, video_id: str) -> dict | None:
        return next(
            (job for job in self.jobs if job["video_id"] == video_id), None
        )

    def enqueue(self, result: SearchResult) -> bool:
        data = _track_data(result)
        if not VIDEO_ID.fullmatch(data["video_id"]) or self.get(data["video_id"]):
            return False
        data.update({
            "playlist_id": str(getattr(result, "playlist_id", "") or ""),
            "status": "queued", "progress": 0, "error": "",
        })
        self.jobs.append(data)
        self._save()
        return True

    def next_queued(self) -> dict | None:
        return next((job for job in self.jobs if job["status"] == "queued"), None)

    def set_status(self, video_id: str, status: str, error: str = "") -> bool:
        job = self.get(video_id)
        if not job or status not in STATES:
            return False
        job["status"] = status
        job["error"] = error
        if status == "queued":
            job["progress"] = 0
        self._save()
        return True

    def set_progress(self, video_id: str, value: int) -> None:
        job = self.get(video_id)
        if not job:
            return
        previous = job["progress"]
        job["progress"] = max(0, min(100, int(value)))
        if job["progress"] == 100 or job["progress"] // 10 > previous // 10:
            self._save()

    def remove(self, video_id: str) -> None:
        self.jobs = [job for job in self.jobs if job["video_id"] != video_id]
        active_playlists = {job["playlist_id"] for job in self.jobs}
        self.playlists = {
            key: value for key, value in self.playlists.items()
            if key in active_playlists
        }
        self._save()

    def remember_playlist(self, playlist: PlaylistResult) -> None:
        self.playlists[playlist.playlist_id] = {
            "playlist_id": playlist.playlist_id,
            "title": playlist.title,
            "channel": playlist.channel,
            "thumbnail_url": playlist.thumbnail_url,
            "url": playlist.url,
            "track_count": playlist.track_count,
            "tracks": [_track_data(track) for track in playlist.tracks],
        }
        self._save()

    def playlist_contexts(self) -> dict[str, PlaylistResult]:
        contexts = {}
        for playlist_id, value in self.playlists.items():
            try:
                tracks = [
                    PlaylistTrack(**track, playlist_id=playlist_id)
                    for track in value.get("tracks", [])
                    if isinstance(track, dict)
                ]
                contexts[playlist_id] = PlaylistResult(
                    playlist_id, value["title"], value["channel"],
                    value.get("thumbnail_url", ""), value["url"],
                    value.get("track_count", len(tracks)), tracks,
                )
            except (KeyError, TypeError, ValueError):
                continue
        return contexts
