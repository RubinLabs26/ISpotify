import unittest
from unittest.mock import patch

from core.discord_presence import (
    DEFAULT_APPLICATION_ID,
    presence_payload,
    valid_application_id,
)
from core.discord_social_sdk import APPLICATION_ID, TokenStore, _friendly_login_error


class DiscordPresenceTests(unittest.TestCase):
    def test_accepts_only_public_numeric_application_ids(self):
        self.assertTrue(valid_application_id("123456789012345678"))
        self.assertFalse(valid_application_id(""))
        self.assertFalse(valid_application_id("a-bot-token-is-not-an-application-id"))
        self.assertFalse(valid_application_id("1234"))

    def test_uses_official_ispotify_application(self):
        self.assertEqual(DEFAULT_APPLICATION_ID, str(APPLICATION_ID))
        self.assertEqual(APPLICATION_ID, 1551266524839411752)

    def test_explains_missing_discord_oauth_configuration(self):
        self.assertIn(
            "http://127.0.0.1/callback",
            _friendly_login_error('OAuth2 Error: Missing "redirect_uri"'),
        )
        self.assertIn(
            "Public Client",
            _friendly_login_error("OAuth2 Error: invalid_client"),
        )

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

    @patch("core.discord_social_sdk.time.time", return_value=1_000)
    @patch("core.discord_social_sdk.keyring.set_password")
    def test_tokens_are_saved_in_the_system_credential_vault(
        self, set_password, _time
    ):
        self.assertTrue(TokenStore().save("access", "refresh", 3600))
        stored = set_password.call_args.args[2]
        self.assertIn('"refresh_token":"refresh"', stored)
        self.assertIn('"expires_at":4600', stored)


if __name__ == "__main__":
    unittest.main()
