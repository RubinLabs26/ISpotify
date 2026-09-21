import tempfile
import threading
import time
import unittest
from pathlib import Path

from core.download_state import DownloadState, result_from_job
from core.downloader import DownloadCancelled, DownloadTask
from core import downloader as downloader_module
from core.searcher import PlaylistResult, PlaylistTrack, SearchResult


class DownloadStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "queue.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_interrupted_active_job_recovers_and_paused_job_stays_paused(self):
        state = DownloadState(self.path)
        first = SearchResult("abcdefghijk", "First", "Artist", "", 120)
        second = SearchResult("lmnopqrstuv", "Second", "Artist", "", 180)
        self.assertTrue(state.enqueue(first))
        self.assertTrue(state.enqueue(second))
        self.assertFalse(state.enqueue(first))
        state.set_status(first.video_id, "active")
        state.set_progress(first.video_id, 40)
        state.set_status(second.video_id, "paused")

        restored = DownloadState(self.path)
        self.assertEqual(restored.get(first.video_id)["status"], "queued")
        self.assertEqual(restored.get(first.video_id)["progress"], 40)
        self.assertEqual(restored.get(second.video_id)["status"], "paused")
        self.assertEqual(restored.next_queued()["video_id"], first.video_id)

    def test_playlist_context_and_failed_job_survive_restart(self):
        track = PlaylistTrack(
            "abcdefghijk", "Track", "Artist", "", 90, "playlist-123"
        )
        playlist = PlaylistResult(
            "playlist-123", "Favorites", "Owner", "", "https://example.com", 1,
            [track],
        )
        state = DownloadState(self.path)
        state.enqueue(track)
        state.remember_playlist(playlist)
        state.set_status(track.video_id, "failed", "Network unavailable")

        restored = DownloadState(self.path)
        job = restored.get(track.video_id)
        self.assertEqual(job["error"], "Network unavailable")
        self.assertEqual(result_from_job(job).playlist_id, "playlist-123")
        self.assertEqual(
            restored.playlist_contexts()["playlist-123"].tracks[0].title,
            "Track",
        )
        restored.remove(track.video_id)
        self.assertEqual(DownloadState(self.path).playlists, {})

    def test_pause_and_cancel_interrupt_progress_hook(self):
        task = DownloadTask("abcdefghijk", "Track")
        progress = []
        task.signals.progress.connect(progress.append)
        task.pause()
        worker = threading.Thread(
            target=lambda: task._progress_hook({
                "status": "downloading", "total_bytes": 100,
                "downloaded_bytes": 50,
            })
        )
        worker.start()
        time.sleep(0.05)
        self.assertTrue(worker.is_alive())
        task.resume()
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())

        task.cancel()
        with self.assertRaises(DownloadCancelled):
            task._progress_hook({"status": "downloading"})

    def test_cancel_removes_only_matching_download_files(self):
        matching = Path(self.temp.name) / "abcdefghijk.webm.part"
        other = Path(self.temp.name) / "lmnopqrstuv.webm.part"
        matching.write_bytes(b"partial")
        other.write_bytes(b"keep")
        original = downloader_module.DOWNLOAD_DIR
        downloader_module.DOWNLOAD_DIR = Path(self.temp.name)
        try:
            downloader_module.discard_download_files("abcdefghijk")
        finally:
            downloader_module.DOWNLOAD_DIR = original
        self.assertFalse(matching.exists())
        self.assertTrue(other.exists())


if __name__ == "__main__":
    unittest.main()
