import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.settings_tab import SettingsTab


class DiscordSettingsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_sdk_owns_browser_launch_and_manual_link_remains_available(self):
        tab = SettingsTab()
        url = "https://discord.com/oauth2/authorize?client_id=123"
        with patch("ui.settings_tab.QDesktopServices.openUrl") as open_url:
            tab.open_discord_authorization(url)
        open_url.assert_not_called()
        self.assertEqual(tab._discord_authorization_url, url)
        self.assertFalse(tab.discord_auth_panel.isHidden())
        tab.close()


if __name__ == "__main__":
    unittest.main()
