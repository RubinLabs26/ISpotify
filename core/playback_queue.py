"""Sequential playback through the local library."""

from __future__ import annotations


class PlaybackQueue:
    def __init__(self):
        self.current: str | None = None
        self.upcoming: list[str] = []
        self.history: list[str] = []

    def start(self, video_id: str, library_order: list[str]) -> None:
        songs = list(dict.fromkeys(item for item in library_order if item))
        if video_id not in songs:
            songs.append(video_id)
        index = songs.index(video_id)
        self.current = video_id
        self.upcoming = songs[index + 1:]
        self.history.clear()

    def next(self) -> str | None:
        if not self.upcoming:
            return None
        if self.current:
            self.history.append(self.current)
        self.current = self.upcoming.pop(0)
        return self.current

    def previous(self) -> str | None:
        if not self.history:
            return None
        if self.current:
            self.upcoming.insert(0, self.current)
        self.current = self.history.pop()
        return self.current
