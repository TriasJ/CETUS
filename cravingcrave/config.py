"""Application configuration and clinical defaults.

These are *bootstrap* defaults. Anything a clinic may want to change at runtime
(crisis phone numbers, session time cap, habituation threshold) is also stored in
the ``app_setting`` table and overrides these once the DB exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import paths

# --- Clinical defaults (overridable via app_setting) -------------------------
# VAS is 0..10. The VR-CET literature habituates "until two consecutive low
# ratings"; we encode that as a configurable threshold + count.
DEFAULT_VAS_MAX = 10
DEFAULT_HABITUATION_THRESHOLD = 2      # rating <= this counts as "low"
DEFAULT_HABITUATION_CONSECUTIVE = 2    # this many consecutive low ratings -> habituated
DEFAULT_PERIODIC_VAS_SECONDS = 30      # periodic craving prompt cadence
DEFAULT_SESSION_TIME_CAP_SECONDS = 20 * 60  # safety cap on a single exposure

# Surfaced on the calm/panic screen. Mexico-oriented defaults; configurable.
DEFAULT_THERAPIST_PHONE = "(Configurar en Ajustes)"
DEFAULT_CRISIS_LINE = "SAPTEL 55 5259-8121"  # national crisis line (Mexico)
DEFAULT_EMERGENCY_NUMBER = "911"

DEFAULT_LOCALE = "es"

# Bootstrap admin-recovery key for the in-app debug/recovery dialog (Ctrl+Shift+A
# on the login screen). Applies only until a clinic sets its own key in the dialog.
# Change this per deployment, or set a custom key in-app. See README.
DEFAULT_ADMIN_KEY = "cetus-admin"


@dataclass
class AppConfig:
    """Resolved runtime configuration."""

    locale: str = DEFAULT_LOCALE
    data_dir: Path = field(default_factory=paths.data_dir)
    media_root: Path = field(default_factory=paths.media_root)
    db_path: Path = field(default_factory=paths.db_path)

    vas_max: int = DEFAULT_VAS_MAX
    habituation_threshold: int = DEFAULT_HABITUATION_THRESHOLD
    habituation_consecutive: int = DEFAULT_HABITUATION_CONSECUTIVE
    periodic_vas_seconds: int = DEFAULT_PERIODIC_VAS_SECONDS
    session_time_cap_seconds: int = DEFAULT_SESSION_TIME_CAP_SECONDS

    # Auto-scroll: advance the shown cue automatically. Both off by default.
    autoscroll_on_grading: bool = False       # advance after a periodic/peak VAS rating
    autoscroll_timed_seconds: int = 0          # 0 = off, else advance every N seconds

    # Accessibility: keyboard-only exposure input (disability keyboard). Off by default.
    accessibility_kbmode: bool = False

    # Adaptive craving prompts (beyond the fixed periodic timer). Both off by default.
    vas_prompt_after_coping: bool = False      # ask craving after each coping (afrontamiento)
    vas_prompt_every_n_cues: int = 0           # 0 = off, else ask craving every N cue advances
    vas_prompt_per_cue_seconds: int = 0        # 0 = off, else prompt after N sec on the SAME cue

    # Cue audio mode: controls whether video/audio cue sound plays during exposure.
    # "auto"       = mute cue audio when ambient sound is active (default; avoids cacophony)
    # "always"     = always play cue audio (even over ambient)
    # "muted"      = always start cue audio muted
    # "audio_only" = play audio only for audio-type cues, mute video audio
    cue_audio_mode: str = "auto"

    # Per-session run defaults (also overridable per session in the Parameters popup).
    default_random_order: bool = False         # randomize the cue order
    default_loop: bool = False                 # loop the cue list at the ends
    default_start_fullscreen: bool = False     # begin the exposure in fullscreen

    # UI theme: light (default) / dark / high_contrast / impaired / classic.
    theme: str = "light"

    # Adaptive cue ordering: learn a per-patient low→high craving hierarchy and offer a
    # clinician-reviewed suggested order in the cue library. Off by default.
    adaptive_ordering: bool = False

    # Progressive down-regulation (experimental): gradually applies a down-regulation
    # lever over the session duration. The progressive value acts as a floor that the
    # patient can increase but not decrease below.
    progressive_downreg_enabled: bool = False
    progressive_downreg_lever: str = "blur"       # "blur" | "shrink" | "dim"
    progressive_downreg_target_pct: int = 10      # % at session end
    progressive_downreg_mode: str = "linear"      # "linear" | "stepped"
    progressive_downreg_step_seconds: int = 10    # for stepped mode: step every N seconds

    # Auto-coping: automatically open the coping panel when the patient records
    # N consecutive high craving scores (>= threshold).
    auto_coping_enabled: bool = False
    auto_coping_threshold: int = 7                # score >= this is "high"
    auto_coping_consecutive: int = 3              # N consecutive highs → auto-open coping

    def ensure_dirs(self) -> None:
        """Create external data/media folders if missing (safe, idempotent)."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.media_root.mkdir(parents=True, exist_ok=True)
        for sub in ("alcohol", "cigarettes", "meth", "positive", "sounds"):
            (self.media_root / sub).mkdir(parents=True, exist_ok=True)
