import unittest
from unittest.mock import patch

from core.discord_presence import presence_payload, valid_application_id


class DiscordPresenceTests(unittest.TestCase):
    def test_accepts_only_public_numeric_application_ids(self):
        self.assertTrue(valid_application_id("123456789012345678"))
        self.assertFalse(valid_application_id(""))
        self.assertFalse(valid_application_id("a-bot-token-is-not-an-application-id"))
        self.assertFalse(valid_application_id("1234"))

    @patch("core.discord_presence.time.time", return_value=2_000)
    def test_builds_listening_activity_with_elapsed_time(self, _time):
        payload = presence_payload(
            {"title": "A Song", "channel": "An Artist"}, 15_000
        )
        self.assertEqual(payload["activity_type"], 2)
        self.assertEqual(payload["details"], "A Song")
        self.assertEqual(payload["state"], "An Artist")
        self.assertEqual(payload["start"], 1_985)

    def test_limits_discord_text_fields(self):
        payload = presence_payload({"title": "x" * 200, "channel": "y" * 200})
        self.assertEqual(len(payload["details"]), 128)
        self.assertEqual(len(payload["state"]), 128)


if __name__ == "__main__":
    unittest.main()
