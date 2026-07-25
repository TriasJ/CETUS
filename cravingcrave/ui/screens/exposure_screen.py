"""The core CET screen: cue + VAS + live chart + intensity + coping + gallery.

Sub-flow inside the screen:
  BASELINE VAS -> graded EXPOSURE (periodic VAS, peak marking, coping, gallery,
  intensity control) -> ENDPOINT VAS -> summary. Panic is handled by the
  MainWindow button, which finalizes the controller and routes to the calm screen.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...domain.models import EndReason, IntensityAction, RatingKind
from ...services.i18n import tr
from ...session.session_controller import SessionController
from .. import hotkeys
from ..context import AppContext
from ..hotkeys import AccessibilityInput
from ..widgets.craving_chart import CravingChart
from ..widgets.cue_view import CueView
from ..widgets.gallery_panel import GalleryPanel
from ..widgets.intensity_controls import IntensityControls
from ..widgets.uscs_panel import UscsPanel
from ..widgets.vas_slider import VasPrompt


class ExposureScreen(QWidget):
    def __init__(self, window, context: AppContext, controller: SessionController,
                 positive_paths: list[str], ambient_path: str | None = None) -> None:
        super().__init__()
        self.window = window
        self.context = context
        self.controller = controller
        self.positive_paths = positive_paths
        self.ambient_path = ambient_path

        self._prompt_open = False
        self._habituated = False
        self._pending_end_reason = EndReason.CLINICIAN_STOP
        self._vas_mode = RatingKind.BASELINE

        # --- widgets --------------------------------------------------------
        self.cue_view = CueView()
        self.cue_view.mediaError.connect(self._on_media_error)

        self.cue_counter = QLabel("")
        self.cue_counter.setObjectName("Muted")
        self.hint = QLabel(tr("exposure.waiting"))
        self.hint.setObjectName("Muted")
        self.hint.setWordWrap(True)

        self.banner = QLabel(tr("endreason.habituated"))
        self.banner.setStyleSheet("background:#e0f2ef; color:#14303a; border-radius:8px; padding:8px;")
        self.banner.setVisible(False)

        # Keyboard-only legend (shown only in accessibility mode).
        self.legend = QLabel(tr("exposure.legend"))
        self.legend.setObjectName("Muted")
        self.legend.setWordWrap(True)
        self.legend.setVisible(False)

        self.chart = CravingChart(context.config.vas_max)
        self.chart.setMinimumHeight(220)
        self.intensity = IntensityControls()
        self.intensity.changed.connect(self._on_intensity)

        self.ambient_btn = QPushButton(tr("exposure.ambient_mute"))
        self.ambient_btn.setCheckable(True)
        self.ambient_btn.toggled.connect(self._on_ambient_mute)
        self.ambient_btn.setVisible(bool(self.ambient_path))

        # --- right panel ----------------------------------------------------
        right = QVBoxLayout()
        right.addWidget(self.chart)
        right.addWidget(self.intensity)
        right.addWidget(self.ambient_btn)
        right_box = QFrame()
        right_box.setLayout(right)
        right_box.setMaximumWidth(380)

        # --- center ---------------------------------------------------------
        center = QVBoxLayout()
        center.addWidget(self.cue_counter)
        center.addWidget(self.cue_view, 1)
        center.addWidget(self.hint)
        center.addWidget(self.legend)
        center.addWidget(self.banner)

        body = QHBoxLayout()
        body.addLayout(center, 1)
        body.addWidget(right_box)

        # --- bottom action bar ---------------------------------------------
        self.peak_btn = QPushButton(tr("exposure.peak_button"))
        self.peak_btn.clicked.connect(self._mark_peak)
        self.coping_btn = QPushButton(tr("exposure.coping"))
        self.coping_btn.clicked.connect(self._open_coping)
        self.gallery_btn = QPushButton(tr("exposure.positive_gallery"))
        self.gallery_btn.clicked.connect(self._open_gallery)
        self.next_btn = QPushButton(tr("exposure.next_cue"))
        self.next_btn.clicked.connect(self._next_cue)
        self.end_btn = QPushButton(tr("exposure.end"))
        self.end_btn.setObjectName("Primary")
        self.end_btn.clicked.connect(self._end_clicked)

        actions = QHBoxLayout()
        for b in (self.peak_btn, self.coping_btn, self.gallery_btn, self.next_btn):
            actions.addWidget(b)
        actions.addStretch(1)
        actions.addWidget(self.end_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.addLayout(body, 1)
        layout.addLayout(actions)

        # --- overlays (children of this screen; panic button stays above) ---
        self.vas_prompt = VasPrompt(self, context.config.vas_max)
        self.vas_prompt.submitted.connect(self._on_vas_submitted)
        self.coping_panel = UscsPanel(self)
        # Keep the raw text (even empty) so "skill used, no text" is distinguishable
        # from "skill skipped" in qualitative exports.
        self.coping_panel.copingRecorded.connect(
            lambda skill, detail: controller.record_coping(skill, detail))
        self.gallery = GalleryPanel(self)
        self.gallery.closed.connect(self._on_gallery_closed)

        # --- timers & signals ----------------------------------------------
        self._timer = QTimer(self)
        self._timer.setInterval(max(1, context.config.periodic_vas_seconds) * 1000)
        self._timer.timeout.connect(self._on_periodic)
        controller.habituationReached.connect(self._on_habituation)

        # Optional timed auto-scroll: advance the cue every N seconds, hands-free.
        self._autoscroll_timer = QTimer(self)
        if context.config.autoscroll_timed_seconds > 0:
            self._autoscroll_timer.setInterval(context.config.autoscroll_timed_seconds * 1000)
            self._autoscroll_timer.timeout.connect(self._on_autoscroll_tick)

        # --- input: standard shortcuts OR keyboard-only accessibility mode --
        self._shortcuts: list[QShortcut] = []
        self._access_input: AccessibilityInput | None = None
        self._install_hotkeys()

        # --- start ----------------------------------------------------------
        controller.begin()
        QTimer.singleShot(0, self._ask_baseline)

    # --- hotkeys / accessibility -------------------------------------------
    def _install_hotkeys(self) -> None:
        """Build exposure input from the resolved hotkey registry. In accessibility
        mode a single application-level key filter drives everything; otherwise the
        standard per-key QShortcuts are installed (identical to the pre-0.4.0 keys)."""
        resolved = hotkeys.resolve_bindings(self.context.repos.settings)
        if self.context.config.accessibility_kbmode:
            self._access_input = AccessibilityInput(self, resolved)
            QApplication.instance().installEventFilter(self._access_input)
            self.legend.setVisible(True)
        else:
            self._install_standard_shortcuts(resolved)

    def _install_standard_shortcuts(self, resolved: dict) -> None:
        slots = {
            "exposure.prev_cue": self._prev_cue,
            "exposure.next_cue": self._next_cue,
            "exposure.size_down": lambda: self.intensity.step_size(-10),
            "exposure.size_up": lambda: self.intensity.step_size(+10),
            "exposure.blur_up": lambda: self.intensity.step_blur(+10),
            "exposure.blur_down": lambda: self.intensity.step_blur(-10),
            "exposure.dim_up": lambda: self.intensity.step_dim(+10),
            "exposure.dim_down": lambda: self.intensity.step_dim(-10),
            "exposure.mute": self.intensity.toggle_mute,
            "exposure.reset": self._reset_intensity,
            "exposure.loop": self._toggle_loop,
        }
        for act in hotkeys.actions_in(hotkeys.Scope.EXPOSURE):
            sc = QShortcut(QKeySequence(resolved[act.id]), self)
            sc.activated.connect(slots[act.id])
            self._shortcuts.append(sc)

    def flash_axis_hint(self) -> None:
        """Prompt the patient (accessibility mode) to pick an axis before +/-."""
        self.hint.setText(tr("exposure.legend_pick_axis"))

    def remove_access_filter(self) -> None:
        if self._access_input is not None:
            QApplication.instance().removeEventFilter(self._access_input)
            self._access_input = None

    def hideEvent(self, event) -> None:
        # Uninstall the application-level key filter when the screen leaves view (stack
        # swap / teardown) so it never lingers on QApplication past this session.
        self.remove_access_filter()
        super().hideEvent(event)

    # --- baseline -----------------------------------------------------------
    def _ask_baseline(self) -> None:
        self._vas_mode = RatingKind.BASELINE
        self._prompt_open = True
        self.vas_prompt.ask(tr("vas.baseline_title"))

    def _begin_exposure(self) -> None:
        self.controller.start_exposure()
        if self.ambient_path:
            self.cue_view.set_ambient(self.ambient_path)
        self._load_cue()
        self.cue_view.set_intensity(100, 0, 0, False)
        self._timer.start()
        if self.context.config.autoscroll_timed_seconds > 0:
            self._autoscroll_timer.start()

    def _on_ambient_mute(self, muted: bool) -> None:
        self.cue_view.set_ambient_muted(muted)
        self.ambient_btn.setText(tr("exposure.ambient_unmute") if muted else tr("exposure.ambient_mute"))
        self.controller.record_intensity(IntensityAction.AMBIENT_MUTE.value, muted=muted)

    # --- cue handling -------------------------------------------------------
    def _load_cue(self) -> None:
        cue = self.controller.current_cue()
        if cue is None:
            return
        abs_path = str(self.context.media.absolute(cue.media_path))
        if cue.media_type == "audio":
            self.cue_view.show_audio(abs_path, Path(cue.media_path).name)
        elif cue.media_type == "video":
            self.cue_view.show_video(abs_path)
        else:
            self.cue_view.show_image(abs_path)
        self.intensity.reset()
        self.cue_view.set_intensity(100, 0, 0, False)
        self.cue_counter.setText(tr("exposure.cue_counter",
                                    current=self.controller.current_cue_index() + 1,
                                    total=self.controller.cue_count))

    def _next_cue(self) -> None:
        self.controller.advance_cue()
        self._load_cue()

    def _prev_cue(self) -> None:
        self.controller.previous_cue()
        self._load_cue()

    def _on_intensity(self, scale: int, blur: int, dim: int, muted: bool, action: str) -> None:
        self.cue_view.set_intensity(scale, blur, dim, muted)
        self.controller.record_intensity(action, scale_pct=scale, blur_pct=blur,
                                         dim_pct=dim, muted=muted)

    def _reset_intensity(self) -> None:
        """R key: snap every lever back to default (100% size, no blur/dim, audible)."""
        self.intensity.reset()
        self.cue_view.set_intensity(100, 0, 0, False)
        self.controller.record_intensity("reset", scale_pct=100, blur_pct=0,
                                         dim_pct=0, muted=False)

    def _toggle_loop(self) -> None:
        """L key: toggle cue-list looping at runtime."""
        self.controller.loop = not self.controller.loop
        self.hint.setText(
            tr("exposure.loop_on" if self.controller.loop else "exposure.loop_off"))

    # --- VAS ----------------------------------------------------------------
    def _on_periodic(self) -> None:
        # Don't interrupt the patient mid-coping or while the positive gallery is open;
        # the timer will prompt again on its next tick once they're back to the cue.
        if self._prompt_open or self.coping_panel.isVisible() or self.gallery.isVisible():
            return
        if self.controller.check_time_cap():
            self._request_end(EndReason.TIME_CAP)
            return
        self.controller.mark_due_periodic()
        self._vas_mode = RatingKind.PERIODIC
        self._prompt_open = True
        self.vas_prompt.ask(tr("vas.periodic_title"))

    def _mark_peak(self) -> None:
        if self._prompt_open:
            return
        self._vas_mode = RatingKind.PEAK
        self._prompt_open = True
        self.vas_prompt.ask(tr("vas.peak_title"))

    def _on_vas_submitted(self, value: int) -> None:
        self._prompt_open = False
        kind = self._vas_mode
        self.controller.record_rating(value, kind)
        self.chart.add_point(self.controller.elapsed_sec(), value)

        if kind is RatingKind.BASELINE:
            self._begin_exposure()
        elif kind is RatingKind.ENDPOINT:
            self._finish(value)
        elif self.context.config.autoscroll_on_grading:
            # After a periodic/peak rating, advance the cue automatically (hands-free).
            self._next_cue()

    def _on_autoscroll_tick(self) -> None:
        # Timed auto-advance; skip while a prompt or a patient panel is up (same guard
        # as the periodic VAS timer) so we never change the cue mid-interaction.
        if self._prompt_open or self.coping_panel.isVisible() or self.gallery.isVisible():
            return
        self._next_cue()

    # --- coping & gallery ---------------------------------------------------
    def _open_coping(self) -> None:
        self.coping_panel.start()

    def _open_gallery(self) -> None:
        self.controller.record_intensity("gallery_open")
        self.gallery.open_with(self.positive_paths)

    def _on_gallery_closed(self) -> None:
        self.controller.record_intensity("gallery_close")

    # --- habituation & ending ----------------------------------------------
    def _on_habituation(self) -> None:
        self._habituated = True
        self.banner.setVisible(True)
        self.end_btn.setText(tr("endreason.habituated"))

    def _end_clicked(self) -> None:
        self._request_end(EndReason.HABITUATED if self._habituated else EndReason.CLINICIAN_STOP)

    def _request_end(self, reason: EndReason) -> None:
        if self._prompt_open:
            return
        self._pending_end_reason = reason
        self._timer.stop()
        self._autoscroll_timer.stop()
        self.controller.go_to_endpoint()
        self._vas_mode = RatingKind.ENDPOINT
        self._prompt_open = True
        self.vas_prompt.ask(tr("vas.endpoint_title"))

    def _finish(self, endpoint_value: int) -> None:
        self.remove_access_filter()
        self.cue_view.stop()
        session = self.controller.finalize(self._pending_end_reason, endpoint_value)
        self.window.show_summary(session, self.controller)

    # --- panic / teardown ---------------------------------------------------
    def stop_timers(self) -> None:
        self._timer.stop()
        self._autoscroll_timer.stop()
        self.remove_access_filter()
        self.cue_view.fade_to_black()

    def _on_media_error(self, path: str) -> None:
        self.hint.setText(tr("error.codec"))
