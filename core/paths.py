"""Linux/XDG paths used by Ishpoitfy.

The original prototype kept its database and audio files beside ``main.py``.
That is convenient for development, but it makes installed copies fragile.
Ishpoitfy keeps user data in the standard XDG data directory and still
understands the prototype's files when it is run from an old checkout.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

APP_NAME = "ishpoitfy"
PROJECT_ROOT = Path(__file__).resolve().parents[1]

_data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
DATA_DIR = _data_home / APP_NAME
DOWNLOAD_DIR = DATA_DIR / "downloads"
LIBRARY_FILE = DATA_DIR / "library.json"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / APP_NAME
COOKIES_FILE = DATA_DIR / "cookies.txt"
COOKIES_RAW_FILE = DATA_DIR / "cookies_raw.txt"


def ensure_directories() -> None:
    """Create the small set of directories needed by the application."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def migrate_legacy_storage() -> None:
    """Copy the prototype's local storage into XDG storage once.

    Nothing is removed from the old checkout. Existing library entries keep
    their original file paths, so this migration is safe even if a user has
    partially downloaded a file.
    """

    ensure_directories()
    legacy_library = PROJECT_ROOT / "library.json"
    if not LIBRARY_FILE.exists() and legacy_library.exists():
        try:
            shutil.copy2(legacy_library, LIBRARY_FILE)
        except OSError:
            pass

    legacy_downloads = PROJECT_ROOT / "downloads"
    if legacy_downloads.exists():
        for source in legacy_downloads.iterdir():
            target = DOWNLOAD_DIR / source.name
            if source.is_file() and not target.exists():
                try:
                    shutil.copy2(source, target)
                except OSError:
                    pass