import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import cookies


LIVE_EXPORT = """[
  {
    "domain": ".youtube.com",
    "name": "SID",
    "value": "test-session",
    "path": "/",
    "secure": true,
    "session": true
  }
]"""


class CookieValidationTests(unittest.TestCase):
    def test_rejects_non_youtube_export(self):
        with self.assertRaisesRegex(cookies.CookieValidationError, "no YouTube"):
            cookies.validate_cookie_text(
                '[{"domain":".example.com","name":"SID","value":"x"}]'
            )

    def test_rejects_expired_login_cookie(self):
        with self.assertRaisesRegex(cookies.CookieValidationError, "no live"):
            cookies.validate_cookie_text(
                '[{"domain":".youtube.com","name":"SID",'
                '"value":"x","expirationDate":1}]'
            )

    def test_accepts_http_only_netscape_rows(self):
        cookies.validate_cookie_text(
            "# Netscape HTTP Cookie File\n"
            "#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tx\n"
        )

    def test_failed_online_check_preserves_previous_files(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie_file = Path(directory) / "cookies.txt"
            raw_file = Path(directory) / "cookies_raw.txt"
            cookie_file.write_text("previous-cookie", encoding="utf-8")
            raw_file.write_text("previous-raw", encoding="utf-8")
            with (
                patch.object(cookies, "COOKIES_FILE", cookie_file),
                patch.object(cookies, "COOKIES_RAW_FILE", raw_file),
                patch.object(cookies, "ensure_directories"),
                patch.object(
                    cookies,
                    "_verify_youtube_session",
                    side_effect=cookies.CookieValidationError("media rejected"),
                ),
            ):
                with self.assertRaises(cookies.CookieValidationError):
                    cookies.validate_and_save_cookies(LIVE_EXPORT)
            self.assertEqual(cookie_file.read_text(encoding="utf-8"), "previous-cookie")
            self.assertEqual(raw_file.read_text(encoding="utf-8"), "previous-raw")

    def test_successful_checks_replace_files(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie_file = Path(directory) / "cookies.txt"
            raw_file = Path(directory) / "cookies_raw.txt"
            with (
                patch.object(cookies, "COOKIES_FILE", cookie_file),
                patch.object(cookies, "COOKIES_RAW_FILE", raw_file),
                patch.object(cookies, "ensure_directories"),
                patch.object(cookies, "_verify_youtube_session"),
            ):
                count, warning = cookies.validate_and_save_cookies(LIVE_EXPORT)
            self.assertEqual(count, 1)
            self.assertEqual(warning, "")
            self.assertIn(".youtube.com\tTRUE\t/\tTRUE\t0\tSID", cookie_file.read_text())
            self.assertEqual(raw_file.read_text(encoding="utf-8"), LIVE_EXPORT)

    def test_authenticated_client_workaround_is_configured(self):
        options = cookies.ydl_youtube_compat_kwargs()
        self.assertEqual(
            options["extractor_args"]["youtube"]["player_client"],
            ["default", "web_embedded"],
        )


if __name__ == "__main__":
    unittest.main()
