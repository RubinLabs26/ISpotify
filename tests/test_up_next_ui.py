import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication

from ui.up_next_tab import UpNextTab


class _Library:
    def find(self, video_id):
        return {"title": video_id, "channel": "Artist"}


class UpNextUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_drag_reorder_emits_visible_song_order(self):
        tab = UpNextTab()
        tab.set_queue("a", ["b", "c", "d"], _Library())
        orders = []
        tab.orderChanged.connect(orders.append)
        self.assertTrue(
            tab.list.model().moveRow(QModelIndex(), 0, QModelIndex(), 3)
        )
        self.assertEqual(orders, [["c", "d", "b"]])
        tab.close()


if __name__ == "__main__":
    unittest.main()
