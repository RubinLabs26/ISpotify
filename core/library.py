"""Small, resilient JSON-backed music library.

Version 8 stored a bare list of songs. Version 9 keeps reading that format and
upgrades it in memory to a document containing songs and playlists.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone

from core.paths import LIBRARY_FILE, migrate_legacy_storage


class Library:
    def __init__(self):
        migrate_legacy_storage()
        self._songs: list[dict] = []
        self._playlists: list[dict] = []
        self._load()

    def _load(self):
        if not LIBRARY_FILE.exists():
            return
        try:
            with LIBRARY_FILE.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                self._songs = data
            elif isinstance(data, dict):
                self._songs = data.get("songs", [])
                self._playlists = data.get("playlists", [])
            else:
                self._songs = []
                self._playlists = []
            if not isinstance(self._songs, list):
                self._songs = []
            if not isinstance(self._playlists, list):
                self._playlists = []
            self._prune_songs()
            self._prune_playlists()
        except (OSError, json.JSONDecodeError):
            self._songs = []
            self._playlists = []

    def _save(self):
        LIBRARY_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix="library-", suffix=".json", dir=LIBRARY_FILE.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({
                    "version": 2,
                    "songs": self._songs,
                    "playlists": self._playlists,
                }, handle, indent=2, ensure_ascii=False)
            os.replace(temp_name, LIBRARY_FILE)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def all_songs(self) -> list[dict]:
        self._prune_songs()
        return list(self._songs)

    def all_playlists(self) -> list[dict]:
        self._prune_playlists()
        return list(self._playlists)

    def find(self, video_id: str) -> dict | None:
        return next((song for song in self._songs if song.get("video_id") == video_id), None)

    def find_playlist(self, playlist_id: str) -> dict | None:
        return next(
            (playlist for playlist in self._playlists
             if playlist.get("playlist_id") == playlist_id),
            None,
        )

    def add_song(self, video_id: str, title: str, channel: str,
                 thumbnail_url: str, file_path: str):
        if not file_path or not os.path.isfile(file_path):
            return
        if self.find(video_id):
            return
        self._songs.append({
            "video_id": video_id,
            "title": title,
            "channel": channel,
            "thumbnail_url": thumbnail_url,
            "file_path": file_path,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "last_played": None,
        })
        self._save()

    def mark_played(self, video_id: str):
        song = self.find(video_id)
        if song:
            song["last_played"] = datetime.now(timezone.utc).isoformat()
            self._save()

    def remove_song(self, video_id: str):
        self._songs = [s for s in self._songs if s.get("video_id") != video_id]
        remaining_playlists = []
        for playlist in self._playlists:
            playlist["tracks"] = [
                track for track in playlist.get("tracks", [])
                if track.get("video_id") != video_id
            ]
            if playlist["tracks"]:
                remaining_playlists.append(playlist)
        self._playlists = remaining_playlists
        self._save()

    def _prune_playlists(self):
        """Keep only playlist tracks that have a real local audio file."""
        downloaded = {
            song.get("video_id")
            for song in self._songs
            if song.get("video_id")
            and song.get("file_path")
            and os.path.isfile(song.get("file_path", ""))
        }
        changed = False
        playlists = []
        for playlist in self._playlists:
            tracks = [
                track for track in playlist.get("tracks", [])
                if track.get("video_id") in downloaded
            ]
            if tracks:
                if len(tracks) != len(playlist.get("tracks", [])):
                    changed = True
                playlist["tracks"] = tracks
                playlists.append(playlist)
            else:
                changed = True
        if changed:
            self._playlists = playlists
            self._save()

    def _prune_songs(self):
        valid_songs = [
            song for song in self._songs
            if song.get("video_id")
            and song.get("file_path")
            and os.path.isfile(song.get("file_path", ""))
        ]
        if len(valid_songs) != len(self._songs):
            self._songs = valid_songs
            self._save()

    def add_playlist(self, playlist_id: str, title: str, channel: str,
                     thumbnail_url: str, url: str, tracks: list):
        """Save playlist metadata and its ordered track references.

        ``tracks`` can be the lightweight objects emitted by Searcher or plain
        dictionaries, which keeps this storage class independent of the UI.
        """
        track_data = []
        seen = set()
        for track in tracks:
            value = track if isinstance(track, dict) else {
                "video_id": getattr(track, "video_id", ""),
                "title": getattr(track, "title", "Unknown title"),
                "channel": getattr(track, "channel", ""),
                "thumbnail_url": getattr(track, "thumbnail_url", ""),
                "duration": getattr(track, "duration", 0),
            }
            video_id = value.get("video_id", "")
            if not video_id or video_id in seen:
                continue
            if not self.find(video_id):
                continue
            seen.add(video_id)
            track_data.append({
                "video_id": video_id,
                "title": value.get("title", "Unknown title"),
                "channel": value.get("channel", channel),
                "thumbnail_url": value.get("thumbnail_url", ""),
                "duration": value.get("duration", 0),
            })

        playlist = self.find_playlist(playlist_id)
        if playlist:
            playlist.update({
                "title": title,
                "channel": channel,
                "thumbnail_url": thumbnail_url,
                "url": url,
                "tracks": track_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        else:
            self._playlists.append({
                "playlist_id": playlist_id,
                "title": title,
                "channel": channel,
                "thumbnail_url": thumbnail_url,
                "url": url,
                "tracks": track_data,
                "added_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        self._save()

    def remove_playlist(self, playlist_id: str):
        self._playlists = [
            playlist for playlist in self._playlists
            if playlist.get("playlist_id") != playlist_id
        ]
        self._save()