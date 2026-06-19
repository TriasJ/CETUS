"""Core domain models and enumerations.

These dataclasses mirror the SQLite schema but carry no persistence logic. ``id``
is ``None`` until a row is written. Enum *values* are the exact strings stored in
the database and written to CSV exports, so they must stay stable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


def utc_now_iso() -> str:
    """ISO-8601 UTC timestamp (stored as TEXT everywhere)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Substance(str, Enum):
    ALCOHOL = "alcohol"
    CIGARETTES = "cigarettes"
    METH = "meth"


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class RatingKind(str, Enum):
    BASELINE = "baseline"
    PERIODIC = "periodic"
    PEAK = "peak"
    ENDPOINT = "endpoint"


class EndReason(str, Enum):
    HABITUATED = "habituated"
    TIME_CAP = "time_cap"
    PANIC = "panic"
    CLINICIAN_STOP = "clinician_stop"


class CopingSkill(str, Enum):
    """The four evidence-based urge-specific coping skills (Monti / Mellentin)."""

    NAME_FEELING = "name_feeling"
    RECALL_NEGATIVE = "recall_negative"
    RECALL_BENEFIT = "recall_benefit"
    ALTERNATIVE_ACTION = "alternative_action"


class IntensityAction(str, Enum):
    SHRINK = "shrink"
    BLUR = "blur"
    DIM = "dim"
    MUTE = "mute"
    AMBIENT_MUTE = "ambient_mute"
    GALLERY_OPEN = "gallery_open"
    GALLERY_CLOSE = "gallery_close"


@dataclass
class Clinician:
    id: Optional[int] = None
    username: str = ""
    display_name: str = ""
    password_hash: str = ""
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class Patient:
    id: Optional[int] = None
    code: str = ""                       # pseudonymous; the ONLY id used in exports
    display_name: Optional[str] = None   # stays in DB, never in export filenames
    birth_year: Optional[int] = None
    primary_substance: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[int] = None
    created_at: str = field(default_factory=utc_now_iso)
    archived: bool = False


@dataclass
class CueConfig:
    id: Optional[int] = None
    patient_id: int = 0
    substance: str = ""
    media_path: str = ""                 # relative to media root
    media_type: str = MediaType.IMAGE.value
    appetitive_rank: int = 0             # graded-escalation order within a session
    enabled: bool = True
    is_personal_reason: bool = False     # patient's "reasons for recovery" image
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class Session:
    id: Optional[int] = None
    patient_id: int = 0
    clinician_id: int = 0
    substance: str = ""
    started_at: str = field(default_factory=utc_now_iso)
    ended_at: Optional[str] = None
    end_reason: Optional[str] = None
    consent_given: bool = False
    baseline_vas: Optional[int] = None
    peak_vas: Optional[int] = None
    endpoint_vas: Optional[int] = None
    habituation_slope: Optional[float] = None
    app_version: str = ""
    clinician_notes: Optional[str] = None


@dataclass
class CravingRating:
    id: Optional[int] = None
    session_id: int = 0
    ts: str = field(default_factory=utc_now_iso)
    elapsed_sec: int = 0
    value: int = 0                       # 0..10 VAS
    kind: str = RatingKind.PERIODIC.value
    cue_config_id: Optional[int] = None


@dataclass
class CopingEvent:
    id: Optional[int] = None
    session_id: int = 0
    ts: str = field(default_factory=utc_now_iso)
    elapsed_sec: int = 0
    skill: str = ""
    detail: Optional[str] = None


@dataclass
class IntensityEvent:
    id: Optional[int] = None
    session_id: int = 0
    ts: str = field(default_factory=utc_now_iso)
    elapsed_sec: int = 0
    action: str = ""
    scale_pct: Optional[int] = None
    blur_pct: Optional[int] = None
    dim_pct: Optional[int] = None
    muted: Optional[bool] = None


@dataclass
class MediaItem:
    """A media file discovered on disk (not necessarily yet a configured cue)."""

    path: str                            # relative to media root
    absolute_path: str
    substance: str                       # folder name: alcohol/cigarettes/meth/positive/sounds
    media_type: str
    filename: str
