import sys
from pathlib import Path

# Keep local imports reliable when launched from a desktop shortcut, a
# different working directory, or an IDE run configuration.
# use it for free
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.theme import install_theme

APP_ORGANIZATION = "Rubin Labs"
APP_COPYRIGHT = "© Rubin Labs"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("iSpotify")
    app.setApplicationDisplayName("iSpotify")
    app.setOrganizationName(APP_ORGANIZATION)
    app.setProperty("copyrightNotice", APP_COPYRIGHT)
    install_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
