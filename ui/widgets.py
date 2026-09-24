"""Reusable lightweight widgets shared by the desktop screens."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import (
    QAbstractAnimation, QEasingCurve, QEvent, QObject, QPointF,
    QPropertyAnimation, QRectF, QSize, Qt, QTimer, QUrl, QVariantAnimation,
)
from PySide6.QtGui import (
    QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect, QLabel, QPushButton,
    QSizePolicy, QStyle,
)

from ui.theme import COLORS, MOTION


def soft_shadow(widget, *, blur: int = 28, y: int = 6, alpha: int = 115):
    """Attach a soft drop shadow to a container widget for layered depth.

    Returns the effect so callers can keep a reference (Qt does not take
    ownership strongly enough to survive GC on its own in every build). Used
    on raised surfaces such as the player bar and cards. Kept off individual
    buttons on purpose: per-button graphics effects are what caused the
    hover-repaint glitches noted on MotionButton.
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setXOffset(0)
    effect.setYOffset(y)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)
    return effect


class HoverLift:
    """Animate a widget's drop-shadow on hover for a subtle, tactile lift.

    Drives only the shadow effect's blur/offset via QPropertyAnimation, never
    the widget's own geometry or event handling, so it cannot interfere with
    click delivery. Install on a container (e.g. an icon button) that already
    carries a soft_shadow-style effect.
    """

    def __init__(self, widget, effect, *, rest_blur=18, rest_y=4,
                 lift_blur=30, lift_y=8):
        self._widget = widget
        self._effect = effect
        self._rest_blur, self._rest_y = rest_blur, rest_y
        self._lift_blur, self._lift_y = lift_blur, lift_y
        self._blur_anim = QPropertyAnimation(effect, b"blurRadius", widget)
        self._y_anim = QPropertyAnimation(effect, b"yOffset", widget)
        for anim in (self._blur_anim, self._y_anim):
            anim.setDuration(MOTION["fast"])
            anim.setEasingCurve(QEasingCurve.OutCubic)
        widget.installEventFilter_target = self  # keep a hard reference

    def to_rest(self):
        self._animate(self._rest_blur, self._rest_y)

    def to_lift(self):
        self._animate(self._lift_blur, self._lift_y)

    def _animate(self, blur, y):
        self._blur_anim.stop()
        self._y_anim.stop()
        self._blur_anim.setEndValue(blur)
        self._y_anim.setEndValue(y)
        self._blur_anim.start()
        self._y_anim.start()


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

_THUMBNAIL_CACHE: dict[str, QPixmap] = {}


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


def thumbnail_pixmap(source: QPixmap, size: QSize) -> QPixmap:
    """Crop a cover image to the tile and apply rounded corners."""
    scaled = source.scaled(
        size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
    )
    x = max(0, (scaled.width() - size.width()) // 2)
    y = max(0, (scaled.height() - size.height()) // 2)
    cropped = scaled.copy(x, y, size.width(), size.height())
    output = QPixmap(size)
    output.fill(Qt.transparent)
    painter = QPainter(output)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size.width(), size.height(), 9, 9)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return output


class MotionButton(QPushButton):
    """A stable button base with reliable native click delivery.

    Motion is intentionally kept in the shared QSS and screen transitions.
    Applying a graphics effect directly to every button caused hover repaint
    glitches on some Qt/Wayland combinations and could swallow release events.
    """

    HOVER_SCALE = 1.12
    PRESS_SCALE = 0.84

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.PointingHandCursor)
        self._icon_base = None
        self._icon_anim = None

    def enable_icon_motion(self) -> None:
        """Let the glyph swell on hover and squish on press.

        Only the icon size is animated, never the button geometry or a
        graphics effect, so layout and click delivery are unaffected. Meant
        for fixed-size icon buttons, where the frame cannot grow with it.
        """
        self._icon_base = QSize(self.iconSize())
        self._icon_anim = QVariantAnimation(self)
        self._icon_anim.valueChanged.connect(self._apply_icon_size)

    def setIconSize(self, size):
        super().setIconSize(size)
        if self._icon_anim is not None:
            self._icon_anim.stop()
            self._icon_base = QSize(size)

    def _apply_icon_size(self, size) -> None:
        if isinstance(size, QSize):
            QPushButton.setIconSize(self, size)

    def _animate_icon(self, scale: float, duration: int, easing) -> None:
        if self._icon_anim is None:
            return
        target = QSize(
            round(self._icon_base.width() * scale),
            round(self._icon_base.height() * scale),
        )
        self._icon_anim.stop()
        self._icon_anim.setDuration(duration)
        self._icon_anim.setEasingCurve(easing)
        self._icon_anim.setStartValue(QSize(self.iconSize()))
        self._icon_anim.setEndValue(target)
        self._icon_anim.start()

    def _rest_scale(self) -> float:
        return self.HOVER_SCALE if self.isEnabled() and self.underMouse() else 1.0

    def enterEvent(self, event):
        super().enterEvent(event)
        if self.isEnabled():
            self._animate_icon(self.HOVER_SCALE, MOTION["base"], QEasingCurve.OutCubic)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._animate_icon(1.0, MOTION["base"], QEasingCurve.OutCubic)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton and self.isEnabled():
            self._animate_icon(self.PRESS_SCALE, 90, QEasingCurve.OutQuad)

    def mouseReleaseEvent(self, event):
        # clicked handlers run inside super(); screens only schedule a
        # replaced button for deletion, so it is still alive afterwards.
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self._animate_icon(self._rest_scale(), 320, QEasingCurve.OutBack)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.EnabledChange:
            # A disabled control should not invite a click.
            self.setCursor(
                Qt.PointingHandCursor if self.isEnabled() else Qt.ArrowCursor
            )
            if not self.isEnabled() and self._icon_anim is not None:
                self._icon_anim.stop()
                QPushButton.setIconSize(self, self._icon_base)


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
    button.enable_icon_motion()
    return button


class SmoothScroller(QObject):
    """Glide a scroll area to each mouse-wheel step instead of jumping.

    Touchpads and high-resolution wheels already deliver pixel-precise
    deltas, so those pass straight through to Qt untouched. Modified wheel
    events (zoom, horizontal) are left alone as well.
    """

    def __init__(self, area):
        super().__init__(area)
        self._bar = area.verticalScrollBar()
        self._target = None
        self._anim = QPropertyAnimation(self._bar, b"value", self)
        self._anim.setDuration(MOTION["slow"])
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._bar.sliderPressed.connect(self._anim.stop)
        area.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Wheel:
            return False
        if (
            event.modifiers() != Qt.NoModifier
            or not event.pixelDelta().isNull()
            or event.phase() != Qt.NoScrollPhase
            or event.angleDelta().y() == 0
        ):
            return False
        bar = self._bar
        if bar.maximum() <= bar.minimum():
            return False
        running = self._anim.state() == QAbstractAnimation.Running
        base = self._target if running and self._target is not None else bar.value()
        step = (
            -event.angleDelta().y() / 120
            * QApplication.wheelScrollLines() * bar.singleStep()
        )
        self._target = max(bar.minimum(), min(bar.maximum(), round(base + step)))
        self._anim.stop()
        self._anim.setStartValue(bar.value())
        self._anim.setEndValue(self._target)
        self._anim.start()
        return True


def enable_smooth_scroll(area) -> SmoothScroller:
    return SmoothScroller(area)


class SlidingIndicator(QFrame):
    """A selection highlight that glides between sibling widgets.

    Sits beneath the tracked widgets (it is transparent to the mouse) and
    re-snaps whenever the parent is shown or resized, so it can never be
    left behind by a layout change.
    """

    def __init__(self, parent, object_name: str = "navIndicator"):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._target = None
        self._anim = QPropertyAnimation(self, b"geometry", self)
        self._anim.setDuration(MOTION["slow"])
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.hide()
        parent.installEventFilter(self)

    def track(self, widget, animate: bool = True) -> None:
        self._target = widget
        if not animate or not self.isVisible() or not self.parentWidget().isVisible():
            self._snap()
            return
        self._anim.stop()
        self._anim.setStartValue(self.geometry())
        self._anim.setEndValue(widget.geometry())
        self._anim.start()

    def _snap(self) -> None:
        if self._target is None:
            return
        self._anim.stop()
        self.setGeometry(self._target.geometry())
        self.lower()
        self.show()

    def _resync(self) -> None:
        if self._target is None:
            return
        if self._anim.state() == QAbstractAnimation.Running:
            # Keep gliding, just toward wherever the layout moved the target.
            self._anim.setEndValue(self._target.geometry())
        else:
            self._snap()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Show, QEvent.Resize, QEvent.LayoutRequest):
            # Wait for the layout to place the tracked widget first.
            QTimer.singleShot(0, self, self._resync)
        return False


class ArtworkLabel(QLabel):
    def __init__(self, title: str, size: QSize, thumbnail_url: str = "", parent=None):
        super().__init__(parent)
        self.title = title
        self.artwork_size = size
        self._thumbnail_url = ""
        self._vinyl = False
        self._spin_angle = 0.0
        self._spin = None
        self._tile_style = ""
        self._network = QNetworkAccessManager(self)
        self.setFixedSize(size)
        self.setPixmap(artwork_pixmap(title, size))
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #1d1d20, stop:1 #151517); "
            f"border: 1px solid {COLORS['border']}; "
            "border-radius: 9px; padding: 0px;"
        )
        self.set_thumbnail(thumbnail_url)

    def set_artwork(self, pixmap: QPixmap) -> None:
        self.setPixmap(thumbnail_pixmap(pixmap, self.artwork_size))

    # -- vinyl mode (a hidden treat, see ui/easter_eggs.py) -----------------

    def is_vinyl(self) -> bool:
        return self._vinyl

    def set_vinyl(self, enabled: bool) -> None:
        """Draw the artwork as the label of a record that can spin."""
        enabled = bool(enabled)
        if enabled == self._vinyl:
            return
        self._vinyl = enabled
        if enabled:
            self._tile_style = self.styleSheet()
            self.setStyleSheet("background: transparent; border: none; padding: 0px;")
            if self._spin is None:
                self._spin = QVariantAnimation(self)
                self._spin.setStartValue(0.0)
                self._spin.setEndValue(360.0)
                self._spin.setDuration(3600)
                self._spin.setLoopCount(-1)
                self._spin.valueChanged.connect(self._set_spin_angle)
        else:
            if self._spin is not None:
                self._spin.stop()
            self._spin_angle = 0.0
            self.setStyleSheet(self._tile_style)
        self.update()

    def set_spinning(self, spinning: bool) -> None:
        if not self._vinyl or self._spin is None:
            return
        state = self._spin.state()
        if spinning:
            if state == QAbstractAnimation.Paused:
                self._spin.resume()
            elif state == QAbstractAnimation.Stopped:
                self._spin.start()
        elif state == QAbstractAnimation.Running:
            self._spin.pause()

    def is_spinning(self) -> bool:
        return (
            self._spin is not None
            and self._spin.state() == QAbstractAnimation.Running
        )

    def _set_spin_angle(self, angle) -> None:
        self._spin_angle = float(angle)
        self.update()

    def paintEvent(self, event):
        if not self._vinyl:
            super().paintEvent(event)
            return
        side = min(self.width(), self.height()) - 2
        center = QPointF(self.width() / 2, self.height() / 2)
        disc = QRectF(center.x() - side / 2, center.y() - side / 2, side, side)
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.Antialiasing | QPainter.SmoothPixmapTransform
        )
        painter.setPen(QPen(QColor(255, 255, 255, 36), 1))
        painter.setBrush(QColor("#0b0b0c"))
        painter.drawEllipse(disc)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 14), 1))
        for ratio in (0.82, 0.68):
            groove = side * ratio / 2
            painter.drawEllipse(center, groove, groove)

        painter.translate(center)
        painter.rotate(self._spin_angle)
        label_radius = side * 0.28
        label = QRectF(-label_radius, -label_radius, label_radius * 2, label_radius * 2)
        clip = QPainterPath()
        clip.addEllipse(label)
        painter.save()
        painter.setClipPath(clip)
        painter.fillRect(label, QColor(COLORS["surface_active"]))
        artwork = self.pixmap()
        if artwork is not None and not artwork.isNull():
            painter.drawPixmap(label, artwork, QRectF(artwork.rect()))
        painter.restore()
        # A small sheen mark so the spin reads even on symmetric artwork.
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1.4, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(
            QRectF(-side * 0.38, -side * 0.38, side * 0.76, side * 0.76),
            30 * 16, 40 * 16,
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(COLORS["background"]))
        painter.drawEllipse(QPointF(0, 0), 2.2, 2.2)
        painter.end()

    def set_thumbnail(self, thumbnail_url: str) -> None:
        """Load remote artwork asynchronously and retain the music-icon fallback."""
        self._thumbnail_url = str(thumbnail_url or "").strip()
        self.setPixmap(artwork_pixmap(self.title, self.artwork_size))
        if not self._thumbnail_url.startswith(("https://", "http://")):
            return
        cached = _THUMBNAIL_CACHE.get(self._thumbnail_url)
        if cached is not None:
            self.set_artwork(cached)
            return
        request = QNetworkRequest(QUrl(self._thumbnail_url))
        request.setRawHeader(b"User-Agent", b"iSpotify/19.1")
        reply = self._network.get(request)
        reply.finished.connect(
            lambda current=reply, url=self._thumbnail_url: self._finish_thumbnail(
                current, url
            )
        )

    def _finish_thumbnail(self, reply, url: str) -> None:
        try:
            data = bytes(reply.readAll())
            pixmap = QPixmap()
            if url == self._thumbnail_url and data and pixmap.loadFromData(data):
                _THUMBNAIL_CACHE[url] = pixmap
                self.set_artwork(pixmap)
        finally:
            reply.deleteLater()


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
