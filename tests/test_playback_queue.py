import unittest
from unittest.mock import patch

from core.playback_queue import PlaybackQueue


class PlaybackQueueTests(unittest.TestCase):
    def test_play_next_reorder_remove_and_clear(self):
        queue = PlaybackQueue()
        queue.start("a", ["a", "b", "c"])
        queue.play_next("c")
        self.assertEqual(queue.upcoming, ["c", "b", "c"])
        self.assertTrue(queue.move(2, -1))
        self.assertEqual(queue.upcoming, ["c", "c", "b"])
        self.assertEqual(queue.next(), "c")
        self.assertEqual(queue.previous(), "a")
        self.assertTrue(queue.remove(1))
        queue.clear()
        self.assertEqual(queue.upcoming, [])

    def test_repeat_one_only_applies_to_automatic_advance(self):
        queue = PlaybackQueue()
        queue.start("a", ["a", "b"])
        queue.cycle_repeat()
        queue.cycle_repeat()
        self.assertEqual(queue.next(automatic=True), "a")
        self.assertEqual(queue.next(), "b")
        self.assertEqual(queue.next(automatic=True), "b")

    def test_repeat_all_and_shuffle(self):
        queue = PlaybackQueue()
        queue.start("a", ["a", "b"])
        queue.cycle_repeat()
        self.assertEqual(queue.next(), "b")
        self.assertEqual(queue.next(automatic=True), "a")
        with patch("core.playback_queue.random.shuffle") as shuffle:
            self.assertTrue(queue.toggle_shuffle())
            shuffle.assert_called_once_with(queue.upcoming)

    def test_drag_order_and_clear_stop_future_tracks(self):
        queue = PlaybackQueue()
        queue.start("a", ["a", "b", "c"])
        self.assertFalse(queue.reorder(["b"]))
        self.assertTrue(queue.reorder(["c", "b"]))
        self.assertEqual(queue.next(), "c")
        queue.cycle_repeat()
        queue.clear()
        self.assertIsNone(queue.next())


if __name__ == "__main__":
    unittest.main()
