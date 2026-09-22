from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, QUrl, Qt, Signal, QSize
from PySide6.QtGui import QFontMetrics
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect, QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget,
)

from ui.theme import SPACE
from ui.widgets import (
    ArtworkLabel, MotionButton, format_duration, icon_button, soft_shadow,
    standard_icon,
)
from core.audio_devices import (
    classify_audio_output,
    headphones_were_disconnected,
    output_kind_label,
)


class PlayerWidget(QWidget):
    trackChanged = Signal(object)
    playbackFailed = Signal(str)
    headphonesDisconnected = Signal(str, bool)
    previousRequested = Signal()
    nextRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("player")
        # A plain QWidget subclass only paints its stylesheet background
        # (surface fill + top divider) when this attribute is set.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.current_song = None
        self._load_token = 0
        self._audio_device_id = None
        self._audio_device_kind = None
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_devices = QMediaDevices(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.7)

        # Lift the persistent transport above the changing page content.
        self._shadow = soft_shadow(self, blur=32, y=-6, alpha=90)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        layout = QHBoxLayout()
        layout.setContentsMargins(SPACE[4], 14, SPACE[4], 14)
        layout.setSpacing(14)
        root.addLayout(layout)
        self.artwork = ArtworkLabel("iSpotify", QSize(46, 46))
        self._artwork_opacity = QGraphicsOpacityEffect(self.artwork)
        self.artwork.setGraphicsEffect(self._artwork_opacity)
        self._artwork_opacity.setOpacity(1.0)
        self._artwork_reveal = QPropertyAnimation(
            self._artwork_opacity, b"opacity", self
        )
        self._artwork_reveal.setDuration(360)
        self._artwork_reveal.setEasingCurve(QEasingCurve.OutCubic)
        layout.addWidget(self.artwork)
        info = QVBoxLayout()
        info.setSpacing(1)
        self.title_label = QLabel("Nothing playing")
        self.title_label.setObjectName("playerTitle")
        self.artist_label = QLabel("Pick something to play")
        self.artist_label.setObjectName("secondary")
        self.output_label = QLabel("Detecting audio outputâ€¦")
        self.output_label.setObjectName("outputDevice")
        info.addStretch()
        info.addWidget(self.title_label)
        info.addWidget(self.artist_label)
        info.addWidget(self.output_label)
        info.addStretch()
        info_wrap = QWidget()
        info_wrap.setLayout(info)
        info_wrap.setFixedWidth(180)
        layout.addWidget(info_wrap)

        self.prev_btn = icon_button("SP_MediaSeekBackward", "Previous track", size=15)
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self.previousRequested.emit)
        layout.addWidget(self.prev_btn)
        self.play_btn = icon_button("SP_MediaPlay", "Play or pause", "playButton", size=18)
        self.play_btn.clicked.connect(self._toggle_play)
        layout.addWidget(self.play_btn)
        self.next_btn = icon_button("SP_MediaSeekForward", "Next track", size=15)
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self.nextRequested.emit)
        layout.addWidget(self.next_btn)

        self.time_label = QLabel("0:00")
        self.time_label.setObjectName("secondary")
        self.time_label.setFixedWidth(36)
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.time_label)
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setMinimumWidth(132)
        self.position_slider.sliderMoved.connect(self.player.setPosition)
        layout.addWidget(self.position_slider, 1)
        self.duration_label = QLabel("0:00")
        self.duration_label.setObjectName("secondary")
        self.duration_label.setFixedWidth(36)
        self.duration_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self.duration_label)

        layout.addSpacing(6)
        volume_icon = QLabel()
        volume_icon.setPixmap(standard_icon("SP_MediaVolume").pixmap(QSize(15, 15)))
        layout.addWidget(volume_icon)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMaximumWidth(80)
        self.volume_slider.valueChanged.connect(
            lambda value: self.audio_output.setVolume(value / 100)
        )
        layout.addWidget(self.volume_slider)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.errorOccurred.connect(self._on_player_error)
        self.media_devices.audioOutputsChanged.connect(self._refresh_audio_device)
        self._audio_device_timer = QTimer(self)
        self._audio_device_timer.setInterval(1500)
        self._audio_device_timer.timeout.connect(self._refresh_audio_device)
        self._audio_device_timer.start()
        self._refresh_audio_device()

    def _refresh_audio_device(self):
        """Follow the system default output and detect unplugged headphones."""
        device = QMediaDevices.defaultAudioOutput()
        name = device.description().strip()
        device_id = bytes(device.id())
        kind = classify_audio_output(name)

        if device_id == self._audio_device_id and kind == self._audio_device_kind:
            return

        previous_kind = self._audio_device_kind
        was_playing = self.player.playbackState() == QMediaPlayer.PlayingState
        disconnected = headphones_were_disconnected(previous_kind, kind)
        if disconnected and was_playing:
            self.player.pause()

        if device_id:
            self.audio_output.setDevice(device)

        self._audio_device_id = device_id
        self._audio_device_kind = kind
        if name:
            label = f"{output_kind_label(kind)} Â· {name}"
            self._elide(self.output_label, label, 168)
            self.output_label.setToolTip(f"Current audio output: {name}")
        else:
            self.output_label.setText("No audio output")
            self.output_label.setToolTip("No system audio output was detected")

        if disconnected:
            self.headphonesDisconnected.emit(name, was_playing)

    @staticmethod
    def _elide(label: QLabel, text: str, width: int) -> None:
        metrics = QFontMetrics(label.font())
        label.setText(metrics.elidedText(text, Qt.ElideRight, width))
        label.setToolTip(text)

    def set_navigation(self, can_go_previous: bool, can_go_next: bool):
        """Enable only the directions that exist in the current library."""
        self.prev_btn.setEnabled(can_go_previous)
        self.next_btn.setEnabled(can_go_next)

    def load_song(self, song: dict):
        self.current_song = song
        self._load_token += 1
        load_token = self._load_token
        self._elide(self.title_label, song.get("title", "Unknown title"), 168)
        self._elide(self.artist_label, song.get("channel", "Unknown artist"), 168)
        self.artwork.title = song.get("title", "iSpotify")
        self.artwork.set_thumbnail(song.get("thumbnail_url", ""))
        self._artwork_reveal.stop()
        self._artwork_reveal.setStartValue(0.15)
        self._artwork_reveal.setEndValue(1.0)
        self._artwork_reveal.start()
        # Explicitly release the previous FFmpeg decoder before replacing it.
        # Without this, rapidly switching between downloaded MP3s can leave
        # two decoders alive and crash some Qt FFmpeg builds on Linux.
        self.player.stop()
        self.player.setSource(QUrl())
        self.play_btn.setIcon(standard_icon("SP_MediaPlay"))
        QTimer.singleShot(0, lambda: self._start_song(song, load_token))
        self.trackChanged.emit(song)

    def refresh_song_metadata(self):
        """Refresh labels after a library rename without restarting playback."""
        if not self.current_song:
            return
        title = self.current_song.get("title", "Unknown title")
        self._elide(self.title_label, title, 168)
        self._elide(
            self.artist_label,
            self.current_song.get("channel", "Unknown artist"),
            168,
        )
        self.artwork.title = title
        self.artwork.set_thumbnail(self.current_song.get("thumbnail_url", ""))

    def _start_song(self, song: dict, load_token: int):
        if load_token != self._load_token:
            return
        self.player.setSource(QUrl.fromLocalFile(song["file_path"]))
        self.player.play()

    def load_and_play(self, file_path: str):
        self.load_song({"title": file_path.rsplit("/", 1)[-1], "channel": "",
                        "file_path": file_path, "video_id": ""})

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_state_changed(self, state):
        self.play_btn.setIcon(
            standard_icon("SP_MediaPause" if state == QMediaPlayer.PlayingState
                          else "SP_MediaPlay")
        )

    def _on_player_error(self, _error, error_string):
        if error_string:
            self.playbackFailed.emit(error_string)

    def closeEvent(self, event):
        self._load_token += 1
        self._audio_device_timer.stop()
        self.player.stop()
        self.player.setSource(QUrl())
        self.audio_output.setVolume(0)
        event.accept()

    def _on_position_changed(self, position_ms):
        self.position_slider.blockSignals(True)
        self.position_slider.setValue(position_ms)
        self.position_slider.blockSignals(False)
        self._update_time_label(position_ms, self.player.duration())

    def _on_duration_changed(self, duration_ms):
        self.position_slider.setRange(0, max(0, duration_ms))
        self._update_time_label(self.player.position(), duration_ms)

    def _update_time_label(self, position_ms, duration_ms):
        self.time_label.setText(format_duration(position_ms / 1000))
        self.duration_label.setText(format_duration(duration_ms / 1000))
