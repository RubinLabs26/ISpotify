"""Reusable lightweight widgets shared by the desktop screens."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QLabel, QPushButton, QSizePolicy, QStyle,
)

from ui.theme import COLORS


def format_duration(seconds: int | float | None) -> str:
    total = max(0, int(seconds or 0))
    return f"{total // 60}:{total % 60:02d}"


def standard_icon(name: str):
    """Return Ishpoitfy's modern line icon, with a Qt fallback."""
    icon_path = Path(__file__).resolve().parents[1] / "assets" / "icons" / f"{name}.svg"
    if icon_path.exists():
        return QIcon(str(icon_path))
    return QApplication.style().standardIcon(getattr(QStyle, name))


def artwork_pixmap(title: str, size: QSize) -> QPixmap:
    """Return the app's audio-only artwork icon, never a cover thumbnail."""

    icon_path = Path(__file__).resolve().parents[1] / "assets" / "icons" / "SP_AudioArtwork.svg"
    return QIcon(str(icon_path)).pixmap(size)


class MotionButton(QPushButton):
    """A stable button base with reliable native click delivery.

    Motion is intentionally kept in the shared QSS and screen transitions.
    Applying a graphics effect directly to every button caused hover repaint
    glitches on some Qt/Wayland combinations and could swallow release events.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


def icon_button(icon_name: str, tooltip: str, object_name: str = "iconButton",
                 size: int = 18) -> MotionButton:
    """A single-purpose, icon-only button. Tooltip carries the label.

    Icon-only controls are used throughout the app wherever the glyph alone
    is unambiguous (play, save, remove, back, expand) so the interface reads
    as calm surfaces rather than a wall of labelled buttons.
    """

    button = MotionButton()
    button.setIcon(standard_icon(icon_name))
    button.setIconSize(QSize(size, size))
    button.setObjectName(object_name)
    button.setToolTip(tooltip)
    button.setCursor(Qt.PointingHandCursor)
    return button


class ArtworkLabel(QLabel):
    def __init__(self, title: str, size: QSize, parent=None):
        super().__init__(parent)
        self.title = title
        self.artwork_size = size
        self.setFixedSize(size)
        self.setPixmap(artwork_pixmap(title, size))
        self.setScaledContents(True)
        self.setStyleSheet(
            f"background-color: {COLORS['surface_raised']}; "
            f"border: 1px solid {COLORS['border']}; "
            "border-radius: 11px; padding: 2px;"
        )

    def set_artwork(self, pixmap: QPixmap) -> None:
        """Keep the display audio-only even when older callers pass an image."""
        self.setPixmap(artwork_pixmap(self.title, self.artwork_size))


class StatusDot(QLabel):
    """A quiet single-glyph status indicator, detail kept in the tooltip.

    Replaces verbose inline labels like "available" / "missing file" with
    a small dot: filled and bright when the state is positive, hollow and
    muted otherwise. Hovering (or a screen reader) still gets the full text.
    """

    def __init__(self, on: bool, on_text: str, off_text: str, parent=None):
        super().__init__("●" if on else "○", parent)
        self.setObjectName("dot")
        self.setProperty("state", "on" if on else "off")
        self.setToolTip(on_text if on else off_text)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedWidth(16)

    def set_state(self, on: bool, on_text: str, off_text: str) -> None:
        self.setText("●" if on else "○")
        self.setProperty("state", "on" if on else "off")
        self.setToolTip(on_text if on else off_text)
        self.style().unpolish(self)
        self.style().polish(self)


class EmptyState(QLabel):
    def __init__(self, title: str, detail: str, parent=None):
        super().__init__(parent)
        self.setObjectName("muted")
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setText(f"<h2 style='color:{COLORS['text']};'>{title}</h2>"
                     f"<p>{detail}</p>")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
