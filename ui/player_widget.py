from __future__ import annotations

from PySide6.QtCore import QTimer, QUrl, Qt, Signal, QSize
from PySide6.QtGui import QFontMetrics
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget,
)

from ui.widgets import (
    ArtworkLabel, artwork_pixmap, format_duration, icon_button,
    standard_icon,
)


class PlayerWidget(QWidget):
    trackChanged = Signal(object)
    playbackFailed = Signal(str)
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
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.7)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        self.artwork = ArtworkLabel("iSpotify", QSize(46, 46))
        layout.addWidget(self.artwork)
        info = QVBoxLayout()
        info.setSpacing(1)
        self.title_label = QLabel("Nothing playing")
        self.title_label.setObjectName("playerTitle")
        self.artist_label = QLabel("Pick something to play")
        self.artist_label.setObjectName("secondary")
        info.addStretch()
        info.addWidget(self.title_label)
        info.addWidget(self.artist_label)
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
        self.artwork.set_artwork(artwork_pixmap(song.get("title", "iSpotify"),
                                                self.artwork.artwork_size))
        # Explicitly release the previous FFmpeg decoder before replacing it.
        # Without this, rapidly switching between downloaded MP3s can leave
        # two decoders alive and crash some Qt FFmpeg builds on Linux.
        self.player.stop()
        self.player.setSource(QUrl())
        self.play_btn.setIcon(standard_icon("SP_MediaPlay"))
        QTimer.singleShot(0, lambda: self._start_song(song, load_token))
        self.trackChanged.emit(song)

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
