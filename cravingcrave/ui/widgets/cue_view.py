"""The cue display surface.

A ``QGraphicsView``/``QGraphicsScene`` holds one content item (image *or* video).
Putting the cue in a graphics scene is what lets all four down-regulation levers
work uniformly:

* **shrink**  -> item scale,
* **blur**    -> ``QGraphicsBlurEffect`` on the item (works on scene items; not on a
  bare ``QVideoWidget``),
* **dim**     -> opacity of a black overlay rect on top,
* **mute**    -> ``QAudioOutput.setMuted``.

The exposure screen only calls :meth:`set_intensity`.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, QSizeF, QUrl, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene,
    QGraphicsView, QWidget,
)

MAX_BLUR_RADIUS = 45.0   # at blur_pct = 100
MAX_DIM_OPACITY = 0.92   # at dim_pct = 100


def _audio_placeholder(label: str) -> QPixmap:
    """A calm card shown while an audio-only cue plays (no black screen)."""
    pix = QPixmap(960, 720)
    pix.fill(QColor("#14303a"))
    p = QPainter(pix)
    p.setPen(QColor("#9be7d8"))
    p.setFont(QFont("Segoe UI", 120, QFont.Weight.Bold))
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "♪")
    p.setPen(QColor("#d7eef0"))
    p.setFont(QFont("Segoe UI", 22))
    p.drawText(QRectF(0, 480, 960, 80), Qt.AlignmentFlag.AlignCenter, label)
    p.end()
    return pix


class CueView(QGraphicsView):
    mediaError = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        self._scene = QGraphicsScene()
        super().__init__(self._scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background:#0e1418; border:none;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._video_item: QGraphicsVideoItem | None = None
        self._base_size: tuple[float, float] = (1.0, 1.0)

        # Dim overlay sits above the cue.
        self._dim = QGraphicsRectItem()
        self._dim.setBrush(QBrush(QColor(0, 0, 0)))
        self._dim.setPen(Qt.PenStyle.NoPen)
        self._dim.setOpacity(0.0)
        self._dim.setZValue(100)
        self._scene.addItem(self._dim)

        self._player: QMediaPlayer | None = None
        self._audio: QAudioOutput | None = None

        # Ambient bed: an independent looping sound layered UNDER the visual cue,
        # persisting across cue changes (session-level). Separate mute from the cue.
        self._ambient_player: QMediaPlayer | None = None
        self._ambient_audio: QAudioOutput | None = None
        self._ambient_muted = False

        # intensity state
        self._scale = 1.0
        self._blur = 0.0
        self._dim_opacity = 0.0
        self._muted = False

    # --- loading ------------------------------------------------------------
    def clear_content(self) -> None:
        if self._player is not None:
            self._player.stop()
        for item in (self._pixmap_item, self._video_item):
            if item is not None:
                self._scene.removeItem(item)
        self._pixmap_item = None
        self._video_item = None

    def show_image(self, path: str) -> None:
        self.clear_content()
        pix = QPixmap(path)
        if pix.isNull():
            self.mediaError.emit(path)
            return
        self._pixmap_item = QGraphicsPixmapItem(pix)
        self._pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._scene.addItem(self._pixmap_item)
        self._base_size = (pix.width(), pix.height())
        self._apply()

    def show_video(self, path: str) -> None:
        self.clear_content()
        self._video_item = QGraphicsVideoItem()
        self._video_item.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self._scene.addItem(self._video_item)
        if self._player is None:
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._player.setAudioOutput(self._audio)
            self._player.errorOccurred.connect(lambda *_: self.mediaError.emit(path))
        self._player.setVideoOutput(self._video_item)
        self._player.setLoops(QMediaPlayer.Loops.Infinite)
        self._player.setSource(QUrl.fromLocalFile(str(Path(path).resolve())))
        self._audio.setMuted(self._muted)
        self._base_size = (1280.0, 720.0)  # display box; aspect kept by the item
        self._apply()
        self._player.play()

    def show_audio(self, path: str, label: str = "") -> None:
        """Standalone audio cue: show a calm ♪ placeholder and play the audio."""
        self.clear_content()
        self._pixmap_item = QGraphicsPixmapItem(_audio_placeholder(label))
        self._scene.addItem(self._pixmap_item)
        self._base_size = (960.0, 720.0)
        if self._player is None:
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._player.setAudioOutput(self._audio)
            self._player.errorOccurred.connect(lambda *_: self.mediaError.emit(path))
        self._player.setVideoOutput(None)
        self._player.setLoops(QMediaPlayer.Loops.Infinite)
        self._player.setSource(QUrl.fromLocalFile(str(Path(path).resolve())))
        self._audio.setMuted(self._muted)
        self._apply()
        self._player.play()

    # --- ambient bed --------------------------------------------------------
    def set_ambient(self, path: str | None) -> None:
        if not path:
            if self._ambient_player is not None:
                self._ambient_player.stop()
            return
        if self._ambient_player is None:
            self._ambient_player = QMediaPlayer(self)
            self._ambient_audio = QAudioOutput(self)
            self._ambient_player.setAudioOutput(self._ambient_audio)
            self._ambient_player.errorOccurred.connect(lambda *_: self.mediaError.emit(path))
        self._ambient_player.setLoops(QMediaPlayer.Loops.Infinite)
        self._ambient_player.setSource(QUrl.fromLocalFile(str(Path(path).resolve())))
        self._ambient_audio.setMuted(self._ambient_muted)
        self._ambient_player.play()

    def set_ambient_muted(self, muted: bool) -> None:
        self._ambient_muted = muted
        if self._ambient_audio is not None:
            self._ambient_audio.setMuted(muted)

    # --- intensity ----------------------------------------------------------
    def set_intensity(self, scale_pct: int, blur_pct: int, dim_pct: int, muted: bool) -> None:
        self._scale = max(0.1, min(1.0, scale_pct / 100.0))
        self._blur = max(0.0, min(1.0, blur_pct / 100.0)) * MAX_BLUR_RADIUS
        self._dim_opacity = max(0.0, min(1.0, dim_pct / 100.0)) * MAX_DIM_OPACITY
        self._muted = muted
        if self._audio is not None:
            self._audio.setMuted(muted)
        self._apply()

    def fade_to_black(self) -> None:
        """Used on panic: hide the cue and silence all audio immediately."""
        self._dim.setOpacity(1.0)
        self.stop()

    def stop(self) -> None:
        if self._player is not None:
            self._player.stop()
        if self._ambient_player is not None:
            self._ambient_player.stop()

    # --- layout -------------------------------------------------------------
    def _content_item(self):
        return self._pixmap_item or self._video_item

    def _apply(self) -> None:
        vw = max(1, self.viewport().width())
        vh = max(1, self.viewport().height())
        self._scene.setSceneRect(0, 0, vw, vh)
        self._dim.setRect(0, 0, vw, vh)
        self._dim.setOpacity(self._dim_opacity)

        item = self._content_item()
        if item is None:
            return

        bw, bh = self._base_size
        fit = min(vw / bw, vh / bh)
        eff = fit * self._scale

        if self._video_item is not None:
            self._video_item.setSize(QSizeF(bw * eff, bh * eff))
            w, h = bw * eff, bh * eff
            self._video_item.setPos((vw - w) / 2, (vh - h) / 2)
        else:
            item.setScale(eff)
            w, h = bw * eff, bh * eff
            item.setPos((vw - w) / 2, (vh - h) / 2)

        if self._blur > 0.0:
            effect = QGraphicsBlurEffect()
            effect.setBlurRadius(self._blur)
            item.setGraphicsEffect(effect)
        else:
            item.setGraphicsEffect(None)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply()
