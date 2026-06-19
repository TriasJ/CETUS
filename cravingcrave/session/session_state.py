"""Explicit session state machine (pure; no Qt).

CONSENT -> BASELINE -> EXPOSURE -> ENDPOINT -> SUMMARY is the normal path.
CALM (panic) is a *global* transition reachable from any active state, which is
why the panic button lives above every screen.
"""

from __future__ import annotations

from enum import Enum, auto


class SessionState(Enum):
    CONSENT = auto()
    BASELINE = auto()
    EXPOSURE = auto()
    ENDPOINT = auto()
    SUMMARY = auto()
    CALM = auto()       # panic destination
    FINISHED = auto()


# States during which a cue is on screen and the patient is actively exposed.
ACTIVE_EXPOSURE_STATES = {SessionState.BASELINE, SessionState.EXPOSURE, SessionState.ENDPOINT}


def can_panic(state: SessionState) -> bool:
    """Panic is allowed from any state where the patient could be exposed."""
    return state in ACTIVE_EXPOSURE_STATES
