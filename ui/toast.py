"""Non-blocking in-app notifications."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QTimer, Qt,
)
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from ui.theme import COLORS


class Toast(QFrame):
    def __init__(self, title: str, detail: str, kind: str, parent=None):
        super().__init__(parent)
        self.setObjectName("toast")
        accent = {
            "success": COLORS["text"],
            "error": COLORS["danger"],
            "warning": COLORS["warning"],
            "info": COLORS["text_secondary"],
        }.get(kind, COLORS["text_secondary"])
        self.setStyleSheet(
            f"""QFrame#toast {{
                background: {COLORS["surface_raised"]};
                border: 1px solid {COLORS["border_bright"]};
                border-radius: 12px;
            }} QFrame#toastBar {{
                background: {accent};
                border-radius: 2px;
            }} QLabel#toastTitle {{
                color: {COLORS["text"]};
                font-weight: 600;
                font-size: 9pt;
            }} QLabel#toastDetail {{
                color: {COLORS["text_secondary"]};
                font-size: 8.5pt;
            }}"""
        )
        layout = QHBoxLayout(self)
        # The accent bar floats inside the rounded frame rather than running
        # edge to edge, where its square ends poked out of the corners.
        layout.setContentsMargins(12, 12, 16, 12)
        layout.setSpacing(11)
        bar = QFrame()
        bar.setObjectName("toastBar")
        bar.setFixedWidth(3)
        layout.addWidget(bar)
        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("toastTitle")
        detail_label = QLabel(detail)
        detail_label.setObjectName("toastDetail")
        detail_label.setWordWrap(True)
        copy.addWidget(title_label)
        if detail:
            copy.addWidget(detail_label)
        layout.addLayout(copy, 1)


class ToastManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet("background: transparent;")
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop | Qt.AlignRight)
        self.layout.setContentsMargins(0, 18, 18, 0)
        self.layout.setSpacing(0)
        self._animations = {}
        self._current_toast = None

    def show_toast(self, title: str, detail: str, kind: str = "info",
                   timeout: int = 4200) -> None:
        # Notifications are intentionally single-slot: a new event replaces
        # the old one instead of building a distracting stack.
        self._remove_current()
        toast = Toast(title, detail, kind, self)
        toast.setMinimumWidth(230)
        toast.setMaximumWidth(320)
        self._current_toast = toast
        effect = QGraphicsOpacityEffect(toast)
        toast.setGraphicsEffect(effect)
        effect.setOpacity(0.0)
        self.layout.addWidget(toast, 0, Qt.AlignRight)
        toast.adjustSize()
        target_height = toast.sizeHint().height()
        toast.setMaximumHeight(0)
        fade_in = QPropertyAnimation(effect, b"opacity", toast)
        fade_in.setDuration(280)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)
        expand = QPropertyAnimation(toast, b"maximumHeight", toast)
        expand.setDuration(320)
        expand.setStartValue(0)
        expand.setEndValue(target_height)
        expand.setEasingCurve(QEasingCurve.OutBack)
        motion = QParallelAnimationGroup(toast)
        motion.addAnimation(fade_in)
        motion.addAnimation(expand)
        motion.start()
        self._animations[toast] = motion
        QTimer.singleShot(timeout, lambda: self._dismiss(toast))

    def _remove_current(self):
        toast = self._current_toast
        if toast is None:
            return
        self._current_toast = None
        animation = self._animations.pop(toast, None)
        if animation:
            animation.stop()
        self.layout.removeWidget(toast)
        toast.hide()
        toast.deleteLater()

    def _dismiss(self, toast):
        if not toast or toast is not self._current_toast or toast.property("closing"):
            return
        toast.setProperty("closing", True)
        self._current_toast = None
        effect = toast.graphicsEffect()
        if not effect:
            toast.deleteLater()
            return
        fade_out = QPropertyAnimation(effect, b"opacity", toast)
        fade_out.setDuration(260)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.InQuad)
        collapse = QPropertyAnimation(toast, b"maximumHeight", toast)
        collapse.setDuration(240)
        collapse.setStartValue(toast.height())
        collapse.setEndValue(0)
        collapse.setEasingCurve(QEasingCurve.InCubic)
        motion = QParallelAnimationGroup(toast)
        motion.addAnimation(fade_out)
        motion.addAnimation(collapse)
        motion.finished.connect(lambda: self._finish(toast))
        self._animations[toast] = motion
        motion.start()

    def _finish(self, toast):
        self._animations.pop(toast, None)
        toast.deleteLater()
