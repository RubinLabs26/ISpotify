import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from core import update_install
from core.updater import is_newer, release_asset, version_tuple
from core.version import APP_VERSION


class UpdaterTests(unittest.TestCase):
    def test_only_newer_stable_versions_are_offered(self):
        self.assertEqual(version_tuple("v19.1.2"), (19, 1, 2))
        self.assertTrue(is_newer("v19.2.1", APP_VERSION))
        self.assertFalse(is_newer("v19.2.0", APP_VERSION))
        self.assertFalse(is_newer("v19.1.1", APP_VERSION))
        self.assertFalse(is_newer("v19.2.0-rc1", APP_VERSION))

    def test_download_requires_trusted_release_url_and_digest(self):
        trusted = {
            "name": "ISpotify-Setup-x86_64.exe",
            "digest": "sha256:" + "a" * 64,
            "browser_download_url": (
                "https://github.com/RubinLabs26/ISpotify/releases/download/"
                "v19.2.0/ISpotify-Setup-x86_64.exe"
            ),
        }
        self.assertEqual(
            release_asset({"assets": [trusted]}, trusted["name"]), trusted
        )
        malicious = dict(trusted, browser_download_url="https://example.com/app.exe")
        self.assertIsNone(release_asset({"assets": [malicious]}, trusted["name"]))
        unsigned = dict(trusted, digest="")
        self.assertIsNone(release_asset({"assets": [unsigned]}, trusted["name"]))

    def test_portable_install_replaces_binary_after_staging(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "ISpotify"
            downloaded = Path(folder) / "new-version"
            target.write_bytes(b"old")
            downloaded.write_bytes(b"new")
            with patch.object(update_install.sys, "executable", str(target)):
                update_install.install_linux_portable(downloaded)
            self.assertEqual(target.read_bytes(), b"new")
            self.assertTrue(downloaded.exists())

    def test_windows_helper_waits_for_exit_and_prompts_after_install(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(update_install, "CACHE_DIR", Path(folder)), patch.object(
                update_install.subprocess, "Popen"
            ) as launch:
                update_install.install_windows(Path(folder) / "setup.exe")
                helper = Path(folder) / "updates" / "install-windows.ps1"
                script = helper.read_text(encoding="utf-8")
                self.assertIn("while (Get-Process -Id $AppPid", script)
                self.assertIn("if ($process.ExitCode -eq 0)", script)
                self.assertIn("Restart now", script)
                launch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
