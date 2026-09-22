"""Session playback order, manual Up Next choices, and repeat behavior."""

from __future__ import annotations

import random
from collections import Counter


class PlaybackQueue:
    def __init__(self):
        self.current: str | None = None
        self.upcoming: list[str] = []
        self.history: list[str] = []
        self.context: list[str] = []
        self.shuffle = False
        self.repeat = "off"

    def start(self, video_id: str, context: list[str]) -> None:
        self.context = list(dict.fromkeys(item for item in context if item))
        if video_id not in self.context:
            self.context.append(video_id)
        index = self.context.index(video_id)
        self.current = video_id
        self.upcoming = self.context[index + 1:] + self.context[:index]
        self.history.clear()
        if self.shuffle:
            random.shuffle(self.upcoming)

    def play_next(self, video_id: str) -> None:
        if video_id:
            self.upcoming.insert(0, video_id)

    def next(self, automatic: bool = False) -> str | None:
        if automatic and self.repeat == "one" and self.current:
            return self.current
        if not self.upcoming and self.repeat == "all" and self.context:
            self.upcoming = list(self.context)
            if self.shuffle:
                random.shuffle(self.upcoming)
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

    def play_at(self, index: int) -> str | None:
        if index < 0 or index >= len(self.upcoming):
            return None
        if self.current:
            self.history.append(self.current)
        self.current = self.upcoming.pop(index)
        return self.current

    def move(self, index: int, offset: int) -> bool:
        target = index + offset
        if index < 0 or target < 0 or target >= len(self.upcoming):
            return False
        self.upcoming[index], self.upcoming[target] = (
            self.upcoming[target], self.upcoming[index]
        )
        return True

    def remove(self, index: int) -> bool:
        if index < 0 or index >= len(self.upcoming):
            return False
        self.upcoming.pop(index)
        return True

    def clear(self) -> None:
        self.upcoming.clear()
        self.context.clear()

    def reorder(self, video_ids: list[str]) -> bool:
        if Counter(video_ids) != Counter(self.upcoming):
            return False
        self.upcoming = list(video_ids)
        return True

    def toggle_shuffle(self) -> bool:
        self.shuffle = not self.shuffle
        if self.shuffle:
            random.shuffle(self.upcoming)
        return self.shuffle

    def cycle_repeat(self) -> str:
        self.repeat = {"off": "all", "all": "one", "one": "off"}[self.repeat]
        return self.repeat
