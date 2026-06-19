"""Orchestrates one exposure session: VAS, cues, coping, intensity, panic, logging.

The controller is a ``QObject`` so screens can react to signals, but every clinical
decision delegates to the pure ``domain`` functions, and all data goes through the
repositories incrementally (so a panic/close still leaves a coherent session).

Elapsed time uses an injectable monotonic clock so the controller can be unit
tested without Qt or wall-clock sleeps.
"""

from __future__ import annotations

import time
from typing import Callable, Optional, Sequence

from PySide6.QtCore import QObject, Signal

from .. import __version__
from ..config import AppConfig
from ..data.repositories import Repositories
from ..domain import habituation
from ..domain.models import (
    Clinician, CopingEvent, CravingRating, CueConfig, EndReason,
    IntensityEvent, Patient, RatingKind, Session, utc_now_iso,
)
from .session_state import SessionState


class SessionController(QObject):
    stateChanged = Signal(object)          # SessionState
    ratingRecorded = Signal(int, str, int)  # value, kind, elapsed_sec
    habituationReached = Signal()
    cueChanged = Signal(int)               # index into exposure playlist
    sessionFinalized = Signal(object)      # Session

    def __init__(
        self,
        repos: Repositories,
        config: AppConfig,
        patient: Patient,
        clinician: Clinician,
        substance: str,
        exposure_cues: Sequence[CueConfig],
        clock: Callable[[], float] = time.monotonic,
        loop: bool = False,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.repos = repos
        self.config = config
        self.patient = patient
        self.clinician = clinician
        self.substance = substance
        self.exposure_cues = list(exposure_cues)
        self._clock = clock
        self.loop = loop  # advance/previous wrap when True

        self.session: Optional[Session] = None
        self.state = SessionState.CONSENT
        self._t0: Optional[float] = None
        self._cue_index = 0
        self._last_periodic_sec = 0.0
        self._values: list[int] = []
        self._peak = 0
        self._baseline: Optional[int] = None
        self._finalized = False

    # --- lifecycle ----------------------------------------------------------
    def begin(self) -> Session:
        """Create the session row (consent already captured) and start the clock."""
        self.session = self.repos.sessions.create(
            Session(
                patient_id=self.patient.id,
                clinician_id=self.clinician.id,
                substance=self.substance,
                consent_given=True,
                app_version=__version__,
            )
        )
        self._t0 = self._clock()
        self._set_state(SessionState.BASELINE)
        return self.session

    def elapsed_sec(self) -> int:
        if self._t0 is None:
            return 0
        return int(self._clock() - self._t0)

    def _set_state(self, state: SessionState) -> None:
        self.state = state
        self.stateChanged.emit(state)

    # --- cues ---------------------------------------------------------------
    @property
    def cue_count(self) -> int:
        return len(self.exposure_cues)

    def current_cue(self) -> Optional[CueConfig]:
        if 0 <= self._cue_index < len(self.exposure_cues):
            return self.exposure_cues[self._cue_index]
        return None

    def current_cue_index(self) -> int:
        return self._cue_index

    def advance_cue(self) -> Optional[CueConfig]:
        if not self.exposure_cues:
            return None
        if self._cue_index < len(self.exposure_cues) - 1:
            self._cue_index += 1
        elif self.loop:
            self._cue_index = 0
        self.cueChanged.emit(self._cue_index)
        return self.current_cue()

    def previous_cue(self) -> Optional[CueConfig]:
        if not self.exposure_cues:
            return None
        if self._cue_index > 0:
            self._cue_index -= 1
        elif self.loop:
            self._cue_index = len(self.exposure_cues) - 1
        self.cueChanged.emit(self._cue_index)
        return self.current_cue()

    # --- ratings ------------------------------------------------------------
    def record_rating(self, raw_value: int, kind: RatingKind) -> CravingRating:
        value = max(0, min(self.config.vas_max, int(raw_value)))
        cue = self.current_cue()
        elapsed = self.elapsed_sec()
        rating = self.repos.ratings.add(
            CravingRating(
                session_id=self.session.id,
                ts=utc_now_iso(),
                elapsed_sec=elapsed,
                value=value,
                kind=kind.value,
                cue_config_id=cue.id if cue else None,
            )
        )
        if kind is RatingKind.BASELINE:
            self._baseline = value
        self._peak = max(self._peak, value)
        # Only craving samples during exposure feed the habituation rule.
        if kind in (RatingKind.PERIODIC, RatingKind.PEAK, RatingKind.ENDPOINT):
            self._values.append(value)
        self.ratingRecorded.emit(value, kind.value, elapsed)

        if kind in (RatingKind.PERIODIC, RatingKind.PEAK) and self.state is SessionState.EXPOSURE:
            if habituation.is_habituated(
                self._values, self.config.habituation_threshold, self.config.habituation_consecutive
            ):
                self.habituationReached.emit()
        return rating

    def start_exposure(self) -> None:
        self._set_state(SessionState.EXPOSURE)

    def mark_due_periodic(self) -> None:
        self._last_periodic_sec = self.elapsed_sec()

    # --- coping & intensity logging ----------------------------------------
    def record_coping(self, skill: str, detail: Optional[str] = None) -> None:
        self.repos.coping.add(
            CopingEvent(session_id=self.session.id, ts=utc_now_iso(),
                        elapsed_sec=self.elapsed_sec(), skill=skill, detail=detail)
        )

    def record_intensity(self, action: str, *, scale_pct=None, blur_pct=None,
                         dim_pct=None, muted=None) -> None:
        self.repos.intensity.add(
            IntensityEvent(session_id=self.session.id, ts=utc_now_iso(),
                           elapsed_sec=self.elapsed_sec(), action=action,
                           scale_pct=scale_pct, blur_pct=blur_pct, dim_pct=dim_pct, muted=muted)
        )

    # --- termination --------------------------------------------------------
    def check_time_cap(self) -> bool:
        """Return True (and nothing else) if the safety time cap has been reached."""
        return self.elapsed_sec() >= self.config.session_time_cap_seconds

    def go_to_endpoint(self) -> None:
        self._set_state(SessionState.ENDPOINT)

    def finalize(self, end_reason: EndReason, endpoint_value: Optional[int] = None) -> Session:
        """Write the closing fields exactly once. Idempotent against double-calls."""
        if self._finalized or self.session is None:
            return self.session
        if endpoint_value is not None:
            self.session.endpoint_vas = max(0, min(self.config.vas_max, int(endpoint_value)))
        ratings = self.repos.ratings.list_for_session(self.session.id)
        points = [(float(r.elapsed_sec), float(r.value)) for r in ratings]
        self.session.habituation_slope = habituation.compute_slope(points)
        self.session.baseline_vas = self._baseline
        self.session.peak_vas = self._peak if self._peak else None
        self.session.ended_at = utc_now_iso()
        self.session.end_reason = end_reason.value
        self.repos.sessions.finalize(self.session)
        self._finalized = True
        self._set_state(SessionState.CALM if end_reason is EndReason.PANIC else SessionState.SUMMARY)
        self.sessionFinalized.emit(self.session)
        return self.session

    def panic(self) -> Session:
        return self.finalize(EndReason.PANIC)

    def clinician_stop(self) -> Session:
        return self.finalize(EndReason.CLINICIAN_STOP)
