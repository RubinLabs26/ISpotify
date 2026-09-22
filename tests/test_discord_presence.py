import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from core.discord_presence import (
    DEFAULT_APPLICATION_ID,
    DOWNLOAD_URL,
    presence_payload,
    valid_application_id,
)
from core.discord_social_sdk import (
    APPLICATION_ID,
    DESKTOP_REDIRECT_URI,
    TokenStore,
    _friendly_login_error,
    authorization_url,
)


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
            str(APPLICATION_ID),
            _friendly_login_error("OAuth2 Error: invalid redirect uri"),
        )
        self.assertIn(
            "Public Client",
            _friendly_login_error("OAuth2 Error: invalid_client"),
        )

    def test_browser_fallback_uses_the_sdk_oauth_parameters(self):
        url = authorization_url("identify sdk.social_layer", "challenge", "state")
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "discord.com")
        self.assertEqual(query["client_id"], [str(APPLICATION_ID)])
        self.assertEqual(query["redirect_uri"], [DESKTOP_REDIRECT_URI])
        self.assertEqual(query["scope"], ["identify sdk.social_layer"])
        self.assertEqual(query["state"], ["state"])
        self.assertEqual(query["code_challenge"], ["challenge"])
        self.assertEqual(query["code_challenge_method"], ["S256"])

    @patch("core.discord_presence.time.time", return_value=2_000)
    def test_builds_listening_activity_with_elapsed_time(self, _time):
        payload = presence_payload(
            {
                "video_id": "abcdefghijk",
                "title": "A Song",
                "channel": "An Artist",
                "duration": 240,
            },
            15_000,
        )
        self.assertEqual(payload["activity_type"], 2)
        self.assertEqual(payload["details"], "A Song")
        self.assertEqual(payload["state"], "An Artist")
        self.assertEqual(payload["start"], 1_985)
        self.assertEqual(payload["end"], 2_225)
        self.assertEqual(
            payload["large_image"],
            "https://i.ytimg.com/vi/abcdefghijk/mqdefault.jpg",
        )
        self.assertEqual(
            payload["url"], "https://www.youtube.com/watch?v=abcdefghijk"
        )
        self.assertEqual(payload["buttons"], [
            {
                "label": "Listen on YouTube",
                "url": "https://www.youtube.com/watch?v=abcdefghijk",
            },
            {"label": "Listen on iSpotify", "url": DOWNLOAD_URL},
        ])

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
