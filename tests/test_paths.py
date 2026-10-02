import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.paths as paths


class StorageMigrationTests(unittest.TestCase):
    def test_migrates_legacy_library_into_xdg_storage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            legacy = root / "legacy" / "library.json"
            target = root / "xdg" / "library.json"
            legacy.parent.mkdir()
            legacy.write_text('{"songs": []}', encoding="utf-8")
            with patch.multiple(
                paths,
                PROJECT_ROOT=root / "legacy",
                DATA_DIR=root / "xdg",
                DOWNLOAD_DIR=root / "xdg" / "downloads",
                CACHE_DIR=root / "cache",
                LIBRARY_FILE=target,
            ):
                paths.migrate_legacy_storage()
            self.assertEqual(target.read_text(encoding="utf-8"), '{"songs": []}')


if __name__ == "__main__":
    unittest.main()
