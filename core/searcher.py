"""Background YouTube song and playlist discovery.

The app deliberately uses yt-dlp and YouTube's public search page instead of
an API key. Playlist searches are parsed from the same result data that
YouTube renders in the browser, while playlist contents are loaded by yt-dlp
so every entry uses the exact same metadata shape as song search.
"""

from __future__ import annotations

import json
import re
import time
from urllib.parse import quote_plus

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from core.cookies import (
    load_requests_cookiejar, ydl_cookie_kwargs, ydl_youtube_compat_kwargs,
)


class SearchResult:
    def __init__(self, video_id, title, channel, thumbnail_url, duration):
        self.video_id = video_id
        self.title = title
        self.channel = channel
        self.thumbnail_url = thumbnail_url
        self.duration = duration
        self.playlist_id = None


class PlaylistTrack(SearchResult):
    def __init__(self, video_id, title, channel="", thumbnail_url="", duration=0,
                 playlist_id=None):
        super().__init__(video_id, title, channel, thumbnail_url, duration)
        self.playlist_id = playlist_id


class PlaylistResult:
    def __init__(self, playlist_id, title, channel, thumbnail_url, url,
                 track_count=0, tracks=None):
        self.playlist_id = playlist_id
        self.title = title
        self.channel = channel
        self.thumbnail_url = thumbnail_url
        self.url = url
        self.track_count = track_count
        self.tracks = tracks or []
        self.next_start = 1
        self.has_more = False


def _text_value(value, fallback="") -> str:
    if isinstance(value, dict):
        if value.get("simpleText"):
            return value["simpleText"]
        return "".join(run.get("text", "") for run in value.get("runs") or [])
    return value or fallback


class SearchWorker(QObject):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, query: str, max_results: int = 20):
        super().__init__()
        self.query = query
        self.max_results = max_results

    def run(self):
        try:
            self.finished.emit(self._search(self.query, self.max_results))
        except Exception as exc:
            self.error.emit(str(exc))

    def _search(self, query: str, max_results: int) -> list[SearchResult]:
        try:
            results = self._search_web(query, max_results)
            if results:
                return results
        except Exception:
            # Keep yt-dlp as a compatibility fallback for older YouTube
            # responses, regional blocks, or temporary web API failures.
            pass

        import yt_dlp

        options = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
            "default_search": "ytsearch",
            "socket_timeout": 10,
            "retries": 1,
        }
        options.update(ydl_youtube_compat_kwargs())
        options.update(ydl_cookie_kwargs())
        results = []
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            for entry in (info or {}).get("entries", []):
                if not entry:
                    continue
                results.append(SearchResult(
                    video_id=entry.get("id", ""),
                    title=entry.get("title", "Unknown title"),
                    channel=entry.get("channel") or entry.get("uploader")
                    or "Unknown channel",
                    thumbnail_url="",
                    duration=entry.get("duration") or 0,
                ))
        return [result for result in results if result.video_id]

    @staticmethod
    def _search_web(query: str, max_results: int) -> list[SearchResult]:
        import requests

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 Ishpoitfy/11"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        session = requests.Session()
        cookie_jar = load_requests_cookiejar()
        if cookie_jar:
            session.cookies = cookie_jar
        page = session.get(
            "https://www.youtube.com/results?search_query="
            f"{quote_plus(query)}",
            headers=headers,
            timeout=10,
        )
        page.raise_for_status()
        api_key = re.search(
            r'"INNERTUBE_API_KEY"\s*:\s*"([^"]+)', page.text
        )
        client_version = re.search(
            r'"INNERTUBE_CLIENT_VERSION"\s*:\s*"([^"]+)', page.text
        )
        if not api_key or not client_version:
            return []
        response = session.post(
            "https://www.youtube.com/youtubei/v1/search",
            params={"key": api_key.group(1)},
            headers={**headers, "Content-Type": "application/json"},
            json={
                "context": {
                    "client": {
                        "clientName": "WEB",
                        "clientVersion": client_version.group(1),
                        "hl": "en",
                        "gl": "US",
                    }
                },
                "query": query,
                "params": "EgIQAQ%3D%3D",
            },
            timeout=10,
        )
        response.raise_for_status()
        results = []
        for entry in SearchWorker._walk_video_renderers(response.json()):
            video_id = entry.get("videoId", "")
            if not video_id:
                continue
            results.append(SearchResult(
                video_id=video_id,
                title=_text_value(entry.get("title"), "Unknown title"),
                channel=_text_value(
                    entry.get("shortBylineText")
                    or entry.get("ownerText"),
                    "Unknown channel",
                ),
                thumbnail_url="",
                duration=_text_value(entry.get("lengthText"), "0"),
            ))
            if len(results) >= max_results:
                break
        for result in results:
            duration = result.duration
            if isinstance(duration, str) and ":" in duration:
                parts = duration.split(":")
                try:
                    result.duration = sum(
                        int(part) * (60 ** index)
                        for index, part in enumerate(reversed(parts))
                    )
                except ValueError:
                    result.duration = 0
        return results

    @staticmethod
    def _walk_video_renderers(value):
        if isinstance(value, dict):
            renderer = value.get("videoRenderer")
            if isinstance(renderer, dict):
                yield renderer
            for child in value.values():
                yield from SearchWorker._walk_video_renderers(child)
        elif isinstance(value, list):
            for child in value:
                yield from SearchWorker._walk_video_renderers(child)


class PlaylistSearchWorker(QObject):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, query: str, max_results: int = 10):
        super().__init__()
        self.query = query
        self.max_results = max_results

    def run(self):
        try:
            self.finished.emit(self._search(self.query, self.max_results))
        except Exception as exc:
            self.error.emit(str(exc))

    @staticmethod
    def _text(value, fallback=""):
        if isinstance(value, dict):
            if value.get("simpleText"):
                return value["simpleText"]
            runs = value.get("runs") or []
            return "".join(run.get("text", "") for run in runs)
        return value or fallback

    def _search(self, query: str, max_results: int) -> list[PlaylistResult]:
        import requests

        # YouTube moved playlist search results from playlistRenderer objects
        # to lockupViewModel objects. The old HTML walk still receives a
        # successful page, but it now finds zero playlists.
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 Ishpoitfy/10"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        session = requests.Session()
        cookie_jar = load_requests_cookiejar()
        if cookie_jar:
            session.cookies = cookie_jar
        page = session.get(
            "https://www.youtube.com/results?search_query="
            f"{quote_plus(query)}",
            headers=headers,
            timeout=15,
        )
        page.raise_for_status()

        api_key = self._match_page_value(page.text, "INNERTUBE_API_KEY")
        client_version = self._match_page_value(
            page.text, "INNERTUBE_CLIENT_VERSION"
        )
        response = None
        data = self._initial_data(page.text)
        if api_key and client_version:
            try:
                response = session.post(
                    "https://www.youtube.com/youtubei/v1/search",
                    params={"key": api_key},
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "context": {
                            "client": {
                                "clientName": "WEB",
                                "clientVersion": client_version,
                                "hl": "en",
                                "gl": "US",
                            }
                        },
                        "query": query,
                        # YouTube's Playlists filter parameter. It is encoded
                        # once in the JSON body, not double-encoded in the URL.
                        "params": "EgIQAw%3D%3D",
                    },
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()
            except (requests.RequestException, ValueError):
                # Older or rate-limited YouTube deployments may not expose
                # the internal endpoint. Keep the legacy HTML parser usable.
                response = None

        results = []
        seen = set()
        candidates = (
            self._walk_playlist_view_models(data)
            if response is not None else
            self._walk_renderers(data)
        )
        for renderer in candidates:
            playlist_id = self._playlist_id(renderer)
            if not playlist_id or playlist_id in seen:
                continue
            seen.add(playlist_id)
            if "lockupViewModel" in renderer:
                model = renderer["lockupViewModel"]
                title = self._view_model_title(model)
                owner = self._view_model_owner(model)
                count_text = self._view_model_count(model)
            else:
                model = renderer
                title = self._text(model.get("title"), "Untitled playlist")
                owner = self._text(model.get("shortBylineText"), "YouTube")
                count_text = self._text(model.get("videoCountText"), "0")
            digits = "".join(char for char in count_text if char.isdigit())
            results.append(PlaylistResult(
                playlist_id=playlist_id,
                title=title,
                channel=owner,
                thumbnail_url="",
                url=f"https://www.youtube.com/playlist?list={playlist_id}",
                track_count=int(digits) if digits else 0,
            ))
            if len(results) >= max_results:
                break
        return results

    @staticmethod
    def _match_page_value(page: str, name: str) -> str:
        match = re.search(
            rf'"{re.escape(name)}"\s*:\s*"([^"]+)"',
            page,
        )
        return match.group(1) if match else ""

    @staticmethod
    def _playlist_id(value: dict) -> str:
        value = value.get("lockupViewModel", value)
        found = []

        def walk(item):
            if isinstance(item, dict):
                if item.get("playlistId"):
                    found.append(item["playlistId"])
                for child in item.values():
                    walk(child)
            elif isinstance(item, list):
                for child in item:
                    walk(child)

        walk(value)
        # WL is a watch-later marker found in menu metadata, not a playlist.
        return next((item for item in found if item != "WL"), "")

    @staticmethod
    def _view_model_title(model: dict) -> str:
        metadata = model.get("metadata") or {}
        lockup = metadata.get("lockupMetadataViewModel") or {}
        title = lockup.get("title") or {}
        return title.get("content") or "Untitled playlist"

    @staticmethod
    def _view_model_texts(model: dict) -> list[str]:
        metadata = (model.get("metadata") or {}).get(
            "lockupMetadataViewModel", {}
        )
        texts = []

        def walk(value):
            if isinstance(value, dict):
                content = value.get("content")
                if isinstance(content, str) and content:
                    texts.append(content)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(metadata.get("metadata", {}))
        return texts

    @classmethod
    def _view_model_owner(cls, model: dict) -> str:
        ignored = {"Playlist", "YouTube Music"}
        metadata = (model.get("metadata") or {}).get(
            "lockupMetadataViewModel", {}
        )
        rows = ((metadata.get("metadata") or {})
                .get("contentMetadataViewModel") or {}).get(
                    "metadataRows", []
                )
        for part in (rows[0].get("metadataParts", []) if rows else []):
            text = (part.get("text") or {}).get("content", "")
            if (
                text
                and text not in ignored
                and "video" not in text.lower()
                and not re.fullmatch(r"\d+:\d+", text)
            ):
                return text
        for text in cls._view_model_texts(model):
            if " · " in text:
                owner = text.split(" · ", 1)[0].strip()
                if owner and owner not in ignored:
                    return owner
        return "YouTube"

    @classmethod
    def _view_model_count(cls, model: dict) -> str:
        for text in cls._view_model_texts(model):
            if "video" in text.lower():
                return text

        def walk(value):
            if isinstance(value, dict):
                text = value.get("text")
                if isinstance(text, str) and "video" in text.lower():
                    return text
                for child in value.values():
                    found = walk(child)
                    if found:
                        return found
            elif isinstance(value, list):
                for child in value:
                    found = walk(child)
                    if found:
                        return found
            return ""

        return walk(model)

    @staticmethod
    def _walk_playlist_view_models(value):
        if isinstance(value, dict):
            if isinstance(value.get("lockupViewModel"), dict):
                yield value
            for child in value.values():
                yield from PlaylistSearchWorker._walk_playlist_view_models(child)
        elif isinstance(value, list):
            for child in value:
                yield from PlaylistSearchWorker._walk_playlist_view_models(child)

    @staticmethod
    def _initial_data(page: str) -> dict:
        decoder = json.JSONDecoder()
        markers = (
            "var ytInitialData = ",
            "ytInitialData = ",
            "window['ytInitialData'] = ",
        )
        for marker in markers:
            start = page.find(marker)
            if start < 0:
                continue
            start += len(marker)
            try:
                value, _ = decoder.raw_decode(page[start:].lstrip())
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                continue
        raise RuntimeError("YouTube did not return playlist search results.")

    @staticmethod
    def _walk_renderers(value):
        if isinstance(value, dict):
            renderer = value.get("playlistRenderer")
            if isinstance(renderer, dict):
                yield renderer
            for child in value.values():
                yield from PlaylistSearchWorker._walk_renderers(child)
        elif isinstance(value, list):
            for child in value:
                yield from PlaylistSearchWorker._walk_renderers(child)


class PlaylistLoadWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, playlist: PlaylistResult, start: int = 1,
                 page_size: int = 50):
        super().__init__()
        self.playlist = playlist
        self.start = max(1, start)
        self.page_size = max(1, page_size)

    def run(self):
        try:
            self.finished.emit(self._load())
        except Exception as exc:
            self.error.emit(str(exc))

    def _load(self) -> PlaylistResult:
        import yt_dlp

        options = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
            "noplaylist": False,
            "lazy_playlist": True,
            "playliststart": self.start,
            "playlistend": self.start + self.page_size - 1,
            "socket_timeout": 10,
            "retries": 1,
        }
        options.update(ydl_youtube_compat_kwargs())
        options.update(ydl_cookie_kwargs())
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(self.playlist.url, download=False)
        tracks = []
        for entry in (info or {}).get("entries", []):
            if not entry or not entry.get("id"):
                continue
            tracks.append(PlaylistTrack(
                video_id=entry["id"],
                title=entry.get("title", "Unknown title"),
                channel=entry.get("channel") or entry.get("uploader")
                or self.playlist.channel,
                thumbnail_url="",
                duration=entry.get("duration") or 0,
                playlist_id=self.playlist.playlist_id,
            ))
        if self.start <= 1:
            self.playlist.tracks = tracks
        else:
            existing_ids = {
                track.video_id for track in self.playlist.tracks
            }
            self.playlist.tracks.extend(
                track for track in tracks if track.video_id not in existing_ids
            )
        total_count = (info or {}).get("playlist_count")
        self.playlist.track_count = (
            total_count or self.playlist.track_count or len(self.playlist.tracks)
        )
        loaded_count = len(self.playlist.tracks)
        self.playlist.next_start = self.start + len(tracks)
        self.playlist.has_more = bool(
            tracks and (
                loaded_count < self.playlist.track_count
                or len(tracks) >= self.page_size
            )
        )
        return self.playlist


class Searcher(QObject):
    """Owns worker thread lifecycles so callers never block the UI."""

    resultsReady = Signal(list)
    playlistsReady = Signal(list)
    playlistReady = Signal(object)
    searchFailed = Signal(str)

    def __init__(self):
        super().__init__()
        self._threads = []
        self._workers = []
        self._cache = {}
        self._cache_ttl = 300

    def _cached(self, key):
        cached = self._cache.get(key)
        if not cached:
            return None
        timestamp, value = cached
        if time.monotonic() - timestamp > self._cache_ttl:
            self._cache.pop(key, None)
            return None
        return list(value)

    def _run_worker(self, worker, finished_signal, cache_key=None):
        if cache_key:
            cached = self._cached(cache_key)
            if cached is not None:
                QTimer.singleShot(0, lambda: finished_signal.emit(cached))
                return

        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        
        def deliver(value):
            if cache_key:
                self._cache[cache_key] = (time.monotonic(), list(value))
            finished_signal.emit(value)

        worker.finished.connect(deliver)
        worker.error.connect(self.searchFailed.emit)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        self._workers.append(worker)
        thread.finished.connect(
            lambda: self._threads.remove(thread)
            if thread in self._threads else None
        )
        thread.finished.connect(
            lambda: self._workers.remove(worker)
            if worker in self._workers else None
        )
        thread.start()

    def search(self, query: str, max_results: int = 20):
        self._run_worker(
            SearchWorker(query, max_results),
            self.resultsReady,
            ("songs", query.casefold(), max_results),
        )

    def search_playlists(self, query: str, max_results: int = 10):
        self._run_worker(
            PlaylistSearchWorker(query, max_results),
            self.playlistsReady,
            ("playlists", query.casefold(), max_results),
        )

    def load_playlist(self, playlist: PlaylistResult, start: int = 1,
                      page_size: int = 50):
        self._run_worker(
            PlaylistLoadWorker(playlist, start, page_size),
            self.playlistReady,
        )
