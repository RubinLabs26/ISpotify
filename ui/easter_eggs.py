"""Hidden delights for curious listeners.

Everything here only *listens*: the filters never consume an event, so a
secret can never swallow a keystroke, click, or scroll that the interface
would otherwise have handled. Typed secrets are ignored while a text field
has focus, so searching for "zen" or "vinyl" behaves exactly as before.
"""

from __future__ import annotations

import time
from collections import deque

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox, QApplication, QComboBox, QLineEdit, QPlainTextEdit,
    QTextEdit,
)


KONAMI_CODE = (
    Qt.Key_Up, Qt.Key_Up, Qt.Key_Down, Qt.Key_Down,
    Qt.Key_Left, Qt.Key_Right, Qt.Key_Left, Qt.Key_Right,
    Qt.Key_B, Qt.Key_A,
)

# Colours cycled through by disco mode. Soft enough to sit on the
# near-monochrome theme without looking like an error state.
DISCO_COLORS = (
    "#ff8fa3", "#ffb86b", "#ffe07a", "#9be7a0",
    "#7fd6ff", "#a99bff", "#f59bea",
)


class SequenceDetector:
    """Report when the most recent tokens exactly match a sequence."""

    def __init__(self, sequence):
        self._sequence = tuple(sequence)
        self._recent = deque(maxlen=len(self._sequence))

    def feed(self, token) -> bool:
        self._recent.append(token)
        if tuple(self._recent) == self._sequence:
            self._recent.clear()
            return True
        return False

    def reset(self) -> None:
        self._recent.clear()


class TapCounter:
    """Report when ``taps`` taps land within ``window`` seconds."""

    def __init__(self, taps: int, window: float, clock=time.monotonic):
        self._taps = taps
        self._window = window
        self._clock = clock
        self._times: deque[float] = deque()

    def tap(self) -> bool:
        now = self._clock()
        while self._times and now - self._times[0] > self._window:
            self._times.popleft()
        self._times.append(now)
        if len(self._times) >= self._taps:
            self._times.clear()
            return True
        return False


class Cooldown:
    """Allow an action at most once per ``seconds``."""

    def __init__(self, seconds: float, clock=time.monotonic):
        self._seconds = seconds
        self._clock = clock
        self._last: float | None = None

    def ready(self) -> bool:
        now = self._clock()
        if self._last is not None and now - self._last < self._seconds:
            return False
        self._last = now
        return True


def _is_text_input(widget) -> bool:
    if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)):
        return True
    return isinstance(widget, QComboBox) and widget.isEditable()


class EasterEggs(QObject):
    """Watch the main window's keyboard for secret sequences."""

    konamiEntered = Signal()
    vinylToggled = Signal()
    zenToggled = Signal()
    escapePressed = Signal()

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._konami = SequenceDetector(KONAMI_CODE)
        self._words = {
            "vinyl": (SequenceDetector("vinyl"), self.vinylToggled),
            "zen": (SequenceDetector("zen"), self.zenToggled),
        }
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and self._is_primary_target(obj):
            self.handle_key(event)
        return False

    def _is_primary_target(self, obj) -> bool:
        # Qt offers a key event to the focus widget and then to each parent
        # that ignores it; an application-wide filter sees every hop. Only
        # the first hop counts, and only inside the main window.
        target = QApplication.focusWidget() or self._window
        if obj is not target:
            return False
        return obj is self._window or obj.window() is self._window

    def handle_key(self, event) -> None:
        if event.isAutoRepeat():
            return
        if event.key() == Qt.Key_Escape:
            self.escapePressed.emit()
            return
        if _is_text_input(QApplication.focusWidget()):
            return
        if self._konami.feed(event.key()):
            self.konamiEntered.emit()
        text = event.text().lower()
        if len(text) != 1 or not text.isprintable():
            return
        for detector, signal in self._words.values():
            if detector.feed(text):
                signal.emit()


class TapWatcher(QObject):
    """Emit ``triggered`` after rapid repeated clicks on watched widgets."""

    triggered = Signal()

    def __init__(self, widgets, taps: int = 5, window: float = 2.0, parent=None):
        super().__init__(parent)
        self._counter = TapCounter(taps, window)
        for widget in widgets:
            widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if (
            event.type() == QEvent.MouseButtonPress
            and event.button() == Qt.LeftButton
            and self._counter.tap()
        ):
            self.triggered.emit()
        return False


class VolumeElevenWatcher(QObject):
    """Emit ``triggered`` when someone tries to push a maxed slider further."""

    triggered = Signal()

    _UP_KEYS = (Qt.Key_Up, Qt.Key_Right, Qt.Key_PageUp)

    def __init__(self, slider, cooldown: float = 4.0, parent=None):
        super().__init__(parent)
        self._slider = slider
        self._cooldown = Cooldown(cooldown)
        slider.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self._slider and self._slider.value() >= self._slider.maximum():
            pushing_up = (
                event.type() == QEvent.Wheel and event.angleDelta().y() > 0
            ) or (
                event.type() == QEvent.KeyPress
                and event.key() in self._UP_KEYS
            )
            if pushing_up and self._cooldown.ready():
                self.triggered.emit()
        return False
