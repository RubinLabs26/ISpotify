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

    def test_release_notes_ignore_dependabot_commands(self):
        notes = release_notes(
            "19.5.1",
            "deps: update keyring",
            4,
            "https://github.com/example/repo/pull/4",
            "## Changes\n"
            "Updated keyring to the latest compatible version.\n\n"
            "<details>\n<summary>Dependabot commands</summary>\n"
            "@dependabot rebase\n</details>",
        )
        self.assertIn("Updated keyring", notes)
        self.assertNotIn("dependabot rebase", notes.lower())


if __name__ == "__main__":
    unittest.main()
