import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import (
    QApplication, QLineEdit, QMainWindow, QSlider, QVBoxLayout, QWidget,
)

from ui.easter_eggs import (
    KONAMI_CODE, Cooldown, EasterEggs, SequenceDetector, TapCounter,
    TapWatcher, VolumeElevenWatcher,
)


def key_event(key, text="", autorepeat=False):
    return QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, text, autorepeat)


def wheel_event(delta_y):
    return QWheelEvent(
        QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, delta_y),
        Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False,
    )


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class DetectorTests(unittest.TestCase):
    def test_sequence_matches_after_noise_and_overlap(self):
        detector = SequenceDetector("zen")
        self.assertFalse(any(detector.feed(c) for c in "zezze"))
        self.assertTrue(detector.feed("n"))
        # A match clears the buffer so it cannot re-fire on the next key.
        self.assertFalse(detector.feed("n"))

    def test_konami_allows_extra_leading_up_presses(self):
        detector = SequenceDetector(KONAMI_CODE)
        results = [detector.feed(k) for k in (Qt.Key_Up,) + KONAMI_CODE]
        self.assertEqual(results[-1], True)
        self.assertEqual(results.count(True), 1)

    def test_tap_counter_requires_taps_inside_window(self):
        clock = FakeClock()
        counter = TapCounter(3, 1.0, clock)
        self.assertFalse(counter.tap())
        clock.now = 0.5
        self.assertFalse(counter.tap())
        clock.now = 2.0  # both earlier taps expired
        self.assertFalse(counter.tap())
        clock.now = 2.2
        self.assertFalse(counter.tap())
        clock.now = 2.4
        self.assertTrue(counter.tap())
        self.assertFalse(counter.tap())

    def test_cooldown(self):
        clock = FakeClock()
        cooldown = Cooldown(4.0, clock)
        self.assertTrue(cooldown.ready())
        clock.now = 3.9
        self.assertFalse(cooldown.ready())
        clock.now = 4.1
        self.assertTrue(cooldown.ready())


class EasterEggFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = QMainWindow()
        central = QWidget()
        layout = QVBoxLayout(central)
        self.field = QLineEdit()
        layout.addWidget(self.field)
        self.window.setCentralWidget(central)
        self.eggs = EasterEggs(self.window)
        self.fired = []
        self.eggs.konamiEntered.connect(lambda: self.fired.append("konami"))
        self.eggs.vinylToggled.connect(lambda: self.fired.append("vinyl"))
        self.eggs.zenToggled.connect(lambda: self.fired.append("zen"))
        self.eggs.escapePressed.connect(lambda: self.fired.append("escape"))

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()

    def type_word(self, word, target=None):
        for char in word:
            event = key_event(ord(char.upper()), char)
            consumed = self.eggs.eventFilter(target or self.window, event)
            self.assertFalse(consumed, "secrets must never swallow keys")

    def test_words_and_konami_fire_without_consuming(self):
        self.type_word("zen")
        self.type_word("vinyl")
        for key in KONAMI_CODE:
            self.assertFalse(self.eggs.eventFilter(self.window, key_event(key)))
        self.assertEqual(self.fired, ["zen", "vinyl", "konami"])

    def test_escape_is_reported(self):
        self.eggs.eventFilter(self.window, key_event(Qt.Key_Escape))
        self.assertEqual(self.fired, ["escape"])

    def test_autorepeat_is_ignored(self):
        for char in "zen":
            self.eggs.eventFilter(
                self.window, key_event(ord(char.upper()), char, autorepeat=True)
            )
        self.assertEqual(self.fired, [])

    def test_only_the_first_delivery_hop_counts(self):
        # With no focus widget, the window is the primary target; a hop
        # through any other widget (propagation) must be ignored.
        for char in "zen":
            event = key_event(ord(char.upper()), char)
            self.eggs.eventFilter(self.field, event)
        self.assertEqual(self.fired, [])

    def test_text_fields_are_left_alone(self):
        from unittest.mock import patch

        with patch("ui.easter_eggs.QApplication.focusWidget", return_value=self.field):
            self.type_word("zen", target=self.field)
        self.assertEqual(self.fired, [])

    def test_other_windows_are_ignored(self):
        from unittest.mock import patch

        other = QWidget()
        with patch("ui.easter_eggs.QApplication.focusWidget", return_value=other):
            self.type_word("zen", target=other)
        other.deleteLater()
        self.assertEqual(self.fired, [])


class WatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_tap_watcher_fires_after_five_quick_clicks(self):
        target = QWidget()
        watcher = TapWatcher([target], taps=5, window=10.0)
        fired = []
        watcher.triggered.connect(lambda: fired.append(True))
        press = QMouseEvent(
            QEvent.MouseButtonPress, QPointF(1, 1), QPointF(1, 1),
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        )
        for _ in range(5):
            self.assertFalse(watcher.eventFilter(target, press))
        self.assertEqual(fired, [True])
        target.deleteLater()

    def test_volume_eleven_only_at_maximum(self):
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(99)
        watcher = VolumeElevenWatcher(slider, cooldown=0)
        fired = []
        watcher.triggered.connect(lambda: fired.append(True))
        self.assertFalse(watcher.eventFilter(slider, wheel_event(120)))
        self.assertEqual(fired, [])
        slider.setValue(100)
        self.assertFalse(watcher.eventFilter(slider, wheel_event(-120)))
        self.assertEqual(fired, [])
        self.assertFalse(watcher.eventFilter(slider, wheel_event(120)))
        self.assertFalse(watcher.eventFilter(slider, key_event(Qt.Key_Up)))
        self.assertEqual(fired, [True, True])
        slider.deleteLater()


class PolishWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_vinyl_artwork_renders_spins_and_restores(self):
        from ui.widgets import ArtworkLabel

        art = ArtworkLabel("Song", QSize(46, 46))
        tile_style = art.styleSheet()
        art.set_spinning(True)  # no-op outside vinyl mode
        self.assertFalse(art.is_spinning())
        art.set_vinyl(True)
        self.assertFalse(art.grab().isNull())
        art.set_spinning(True)
        self.assertTrue(art.is_spinning())
        art.set_spinning(False)
        self.assertFalse(art.is_spinning())
        art.set_spinning(True)
        self.assertTrue(art.is_spinning())
        art.set_vinyl(False)
        self.assertFalse(art.is_spinning())
        self.assertEqual(art.styleSheet(), tile_style)
        self.assertFalse(art.grab().isNull())
        art.deleteLater()

    def test_icon_motion_returns_to_base_size(self):
        from ui.widgets import icon_button

        button = icon_button("SP_MediaPlay", "Play", "playButton", size=18)
        button._animate_icon(button.HOVER_SCALE, 10, QEasingCurve.Linear)
        button._icon_anim.setCurrentTime(button._icon_anim.duration())
        self.assertEqual(button.iconSize(), QSize(20, 20))
        button._animate_icon(1.0, 10, QEasingCurve.Linear)
        button._icon_anim.setCurrentTime(button._icon_anim.duration())
        self.assertEqual(button.iconSize(), QSize(18, 18))
        # Disabling mid-animation snaps the glyph back to its resting size.
        button._animate_icon(button.PRESS_SCALE, 1000, QEasingCurve.Linear)
        button._icon_anim.setCurrentTime(500)
        button.setEnabled(False)
        self.assertEqual(button.iconSize(), QSize(18, 18))
        # An explicit resize becomes the new resting size.
        button.setIconSize(QSize(24, 24))
        button._animate_icon(1.0, 10, QEasingCurve.Linear)
        button._icon_anim.setCurrentTime(button._icon_anim.duration())
        self.assertEqual(button.iconSize(), QSize(24, 24))
        button.deleteLater()

    def test_smooth_scroller_glides_and_clamps(self):
        from PySide6.QtWidgets import QScrollArea

        from ui.widgets import enable_smooth_scroll

        area = QScrollArea()
        area.setWidgetResizable(True)
        content = QWidget()
        content.setMinimumHeight(4000)
        area.setWidget(content)
        area.resize(300, 300)
        area.show()
        self.app.processEvents()
        scroller = enable_smooth_scroll(area)
        bar = area.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        self.assertTrue(scroller.eventFilter(area.viewport(), wheel_event(-120)))
        scroller._anim.setCurrentTime(scroller._anim.duration())
        expected = QApplication.wheelScrollLines() * bar.singleStep()
        self.assertEqual(bar.value(), expected)
        # Scrolling up past the top clamps at the minimum.
        for _ in range(5):
            scroller.eventFilter(area.viewport(), wheel_event(120))
        scroller._anim.setCurrentTime(scroller._anim.duration())
        self.assertEqual(bar.value(), bar.minimum())
        # Touchpad-style pixel deltas are left to Qt.
        pixel = QWheelEvent(
            QPointF(5, 5), QPointF(5, 5), QPoint(0, -30), QPoint(0, -120),
            Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False,
        )
        self.assertFalse(scroller.eventFilter(area.viewport(), pixel))
        area.close()
        area.deleteLater()

    def test_sliding_indicator_follows_target(self):
        from ui.widgets import MotionButton, SlidingIndicator

        host = QWidget()
        layout = QVBoxLayout(host)
        first, second = MotionButton("One"), MotionButton("Two")
        layout.addWidget(first)
        layout.addWidget(second)
        indicator = SlidingIndicator(host)
        indicator.track(first)
        host.resize(200, 200)
        host.show()
        self.app.processEvents()
        self.app.processEvents()
        self.assertTrue(indicator.isVisible())
        self.assertEqual(indicator.geometry(), first.geometry())
        indicator.track(second)
        indicator._anim.setCurrentTime(indicator._anim.duration())
        self.assertEqual(indicator.geometry(), second.geometry())
        host.close()
        host.deleteLater()

    def test_download_progress_glides_forward_and_jumps_back(self):
        from ui.downloads_tab import DownloadRow

        row = DownloadRow({
            "video_id": "abc", "title": "Song", "status": "active", "progress": 30,
        })
        self.assertEqual(row.progress.value(), 30)  # hidden rows jump
        row.show()
        row.set_progress(80)
        self.assertEqual(row._progress_anim.endValue(), 80)
        row._progress_anim.setCurrentTime(row._progress_anim.duration())
        self.assertEqual(row.progress.value(), 80)
        row.set_progress(10)
        self.assertEqual(row.progress.value(), 10)
        row.close()
        row.deleteLater()


if __name__ == "__main__":
    unittest.main()
