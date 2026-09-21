import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.library as library_module
from core.library import Library


class LibraryPlaylistTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.library_file = self.root / "library.json"
        self.file_one = self.root / "one.mp3"
        self.file_two = self.root / "two.mp3"
        self.file_one.write_bytes(b"one")
        self.file_two.write_bytes(b"two")
        self.path_patch = patch.object(
            library_module, "LIBRARY_FILE", self.library_file
        )
        self.migration_patch = patch.object(
            library_module, "migrate_legacy_storage"
        )
        self.path_patch.start()
        self.migration_patch.start()

    def tearDown(self):
        self.migration_patch.stop()
        self.path_patch.stop()
        self.temp_dir.cleanup()

    def make_library(self):
        library = Library()
        library.add_song("one", "Song One", "Artist", "", str(self.file_one))
        library.add_song("two", "Song Two", "Artist", "", str(self.file_two))
        return library

    def test_empty_manual_playlist_survives_reload_and_song_removal(self):
        library = self.make_library()
        playlist = library.create_playlist("Road trip")
        self.assertTrue(
            library.add_song_to_playlist(playlist["playlist_id"], "one")
        )
        library.remove_song("one")

        reloaded = Library()
        stored = reloaded.find_playlist(playlist["playlist_id"])
        self.assertIsNotNone(stored)
        self.assertEqual(stored["title"], "Road trip")
        self.assertEqual(stored["tracks"], [])

    def test_rename_and_reorder_playlist_tracks(self):
        library = self.make_library()
        playlist = library.create_playlist("Original")
        playlist_id = playlist["playlist_id"]
        library.add_song_to_playlist(playlist_id, "one")
        library.add_song_to_playlist(playlist_id, "two")

        self.assertTrue(library.rename_playlist(playlist_id, "Favorites"))
        self.assertTrue(library.rename_song("one", "First song"))
        self.assertTrue(library.move_playlist_track(playlist_id, "two", -1))

        stored = library.find_playlist(playlist_id)
        self.assertEqual(stored["title"], "Favorites")
        self.assertEqual(
            [track["video_id"] for track in stored["tracks"]],
            ["two", "one"],
        )
        self.assertEqual(stored["tracks"][1]["title"], "First song")

    def test_moves_song_between_playlists_without_duplicates(self):
        library = self.make_library()
        source = library.create_playlist("Source")
        target = library.create_playlist("Target")
        library.add_song_to_playlist(source["playlist_id"], "one")
        library.add_song_to_playlist(target["playlist_id"], "one")

        self.assertTrue(library.move_song_to_playlist(
            source["playlist_id"], target["playlist_id"], "one"
        ))
        self.assertEqual(source["tracks"], [])
        self.assertEqual(
            [track["video_id"] for track in target["tracks"]], ["one"]
        )

    def test_new_song_keeps_duration_and_gets_thumbnail_fallback(self):
        library = Library()
        library.add_song(
            "abcdefghijk", "Song", "Artist", "", str(self.file_one), 245
        )

        song = library.find("abcdefghijk")
        self.assertEqual(song["duration"], 245)
        self.assertEqual(
            song["thumbnail_url"],
            "https://i.ytimg.com/vi/abcdefghijk/mqdefault.jpg",
        )


if __name__ == "__main__":
    unittest.main()
