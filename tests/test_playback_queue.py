import unittest

from core.playback_queue import PlaybackQueue


class PlaybackQueueTests(unittest.TestCase):
    def test_plays_remaining_library_tracks_in_order(self):
        playback = PlaybackQueue()
        playback.start("b", ["a", "b", "c", "d"])
        self.assertEqual(playback.upcoming, ["c", "d"])
        self.assertEqual(playback.next(), "c")
        self.assertEqual(playback.next(), "d")
        self.assertIsNone(playback.next())

    def test_previous_returns_to_prior_song_then_resumes_order(self):
        playback = PlaybackQueue()
        playback.start("a", ["a", "b", "c"])
        self.assertEqual(playback.next(), "b")
        self.assertEqual(playback.previous(), "a")
        self.assertEqual(playback.next(), "b")
        self.assertEqual(playback.next(), "c")

    def test_starting_another_song_resets_sequence(self):
        playback = PlaybackQueue()
        playback.start("a", ["a", "b", "c"])
        playback.next()
        playback.start("b", ["a", "b", "b", "c"])
        self.assertEqual(playback.upcoming, ["c"])
        self.assertEqual(playback.history, [])


if __name__ == "__main__":
    unittest.main()
