import unittest

from tools.release_bot import bump_version, release_notes


class ReleaseBotTests(unittest.TestCase):
    def test_semantic_version_bumps(self):
        self.assertEqual(bump_version("19.4.0", "patch"), "19.4.1")
        self.assertEqual(bump_version("19.4.7", "minor"), "19.5.0")
        self.assertEqual(bump_version("19.4.7", "major"), "20.0.0")

    def test_release_notes_exclude_validation_noise(self):
        notes = release_notes(
            "19.5.0",
            "Add a useful feature",
            31,
            "https://github.com/example/repo/pull/31",
            "## Changes\n- Adds the feature.\n## Validation\n- 99 tests pass.",
        )
        self.assertIn("Adds the feature", notes)
        self.assertNotIn("99 tests", notes)
        self.assertIn("ispotify_19.5.0_amd64.deb", notes)


if __name__ == "__main__":
    unittest.main()
