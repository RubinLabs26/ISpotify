"""Reusable lightweight widgets shared by the desktop screens."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QLabel, QPushButton, QSizePolicy, QStyle,
)

from ui.theme import COLORS


PLAYLIST_GRADIENTS = (
    ("#7c2d4f", "#d65382"),
    ("#224e77", "#3d8ac4"),
    ("#2d664f", "#45a276"),
    ("#69409a", "#9a67d2"),
    ("#8a4725", "#df8242"),
    ("#285f6f", "#45a7b4"),
    ("#6e3438", "#c75757"),
    ("#4e5f27", "#8aa33d"),
    ("#433b8f", "#7667d8"),
    ("#8b305f", "#d85b91"),
    ("#91651c", "#dfaa3f"),
    ("#31557e", "#4f86bd"),
)


def playlist_colors(seed: str) -> tuple[str, str]:
    """Return a stable, high-contrast gradient for a playlist identifier."""
    digest = hashlib.sha256(str(seed or "playlist").encode("utf-8")).digest()
    value = int.from_bytes(digest[:4], "big")
    return PLAYLIST_GRADIENTS[value % len(PLAYLIST_GRADIENTS)]


def format_duration(seconds: int | float | None) -> str:
    total = max(0, int(seconds or 0))
    return f"{total // 60}:{total % 60:02d}"


def standard_icon(name: str):
    """Return Ishpoitfy's modern line icon, with a Qt fallback."""
    icon_dir = Path(__file__).resolve().parents[1] / "assets" / "icons"
    icon_path = icon_dir / f"{name}.svg"
    if icon_path.exists():
        icon = QIcon(str(icon_path))
        # A glyph may ship its own disabled look (<name>_disabled.svg). Used
        # where the normal glyph is dark-on-light, because Qt's automatic
        # dimming would otherwise sink it into a dark disabled background.
        disabled_path = icon_dir / f"{name}_disabled.svg"
        if disabled_path.exists():
            icon.addFile(str(disabled_path), QSize(), QIcon.Disabled)
        return icon
    return QApplication.style().standardIcon(getattr(QStyle, name))


def artwork_pixmap(title: str, size: QSize) -> QPixmap:
    """Return the app's audio-only artwork, never a cover thumbnail.

    A quiet note glyph centred on a transparent canvas of exactly ``size``.
    The tile itself (fill, border, radius) is drawn by ArtworkLabel, so the
    glyph keeps its true proportions in every tile shape instead of being
    stretched to fit a 4:3 frame.
    """

    glyph_path = Path(__file__).resolve().parents[1] / "assets" / "icons" / "SP_AudioGlyph.svg"
    side = max(14, round(min(size.width(), size.height()) * 0.44))
    glyph = QIcon(str(glyph_path)).pixmap(QSize(side, side))
    ratio = glyph.devicePixelRatio() or 1.0
    canvas = QPixmap(round(size.width() * ratio), round(size.height() * ratio))
    canvas.setDevicePixelRatio(ratio)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    painter.drawPixmap(
        round((size.width() - glyph.width() / ratio) / 2),
        round((size.height() - glyph.height() / ratio) / 2),
        glyph,
    )
    painter.end()
    return canvas


class MotionButton(QPushButton):
    """A stable button base with reliable native click delivery.

    Motion is intentionally kept in the shared QSS and screen transitions.
    Applying a graphics effect directly to every button caused hover repaint
    glitches on some Qt/Wayland combinations and could swallow release events.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.PointingHandCursor)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.EnabledChange:
            # A disabled control should not invite a click.
            self.setCursor(
                Qt.PointingHandCursor if self.isEnabled() else Qt.ArrowCursor
            )


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
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #1d1d20, stop:1 #151517); "
            f"border: 1px solid {COLORS['border']}; "
            "border-radius: 9px; padding: 0px;"
        )

    def set_artwork(self, pixmap: QPixmap) -> None:
        """Keep the display audio-only even when older callers pass an image."""
        self.setPixmap(artwork_pixmap(self.title, self.artwork_size))


class PlaylistArtworkLabel(QLabel):
    """A persistent colored playlist cover derived from its stable ID."""

    def __init__(self, title: str, seed: str, size: QSize, parent=None):
        super().__init__(parent)
        self.setFixedSize(size)
        self.setAlignment(Qt.AlignCenter)
        self.setToolTip(title)
        start, end = playlist_colors(seed)
        self.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {start}, stop:1 {end}); "
            "border: 1px solid rgba(255, 255, 255, 0.16); "
            "border-radius: 9px; padding: 0px;"
        )
        icon_path = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "icons"
            / "SP_PlaylistGlyph.svg"
        )
        icon_side = max(18, round(min(size.width(), size.height()) * 0.42))
        self.setPixmap(QIcon(str(icon_path)).pixmap(QSize(icon_side, icon_side)))


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
        self.setText(
            f"<p style='margin:0; font-size:12.5pt; font-weight:600; "
            f"color:{COLORS['text']};'>{title}</p>"
            f"<p style='margin:6px 0 0 0; font-size:9.5pt; "
            f"line-height:135%; color:{COLORS['text_secondary']};'>{detail}</p>"
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
