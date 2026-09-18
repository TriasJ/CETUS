"""Dependency bundle passed to every screen.

Holds the wired services and the currently logged-in clinician. Created once at
startup in ``app.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import AppConfig
from ..data.database import Database
from ..data.repositories import Repositories
from ..domain.models import Clinician
from ..services.auth import AuthService
from ..services.crisis import CrisisService
from ..services.media_library import MediaLibrary


@dataclass
class AppContext:
    config: AppConfig
    db: Database
    repos: Repositories
    auth: AuthService
    crisis: CrisisService
    media: MediaLibrary
    clinician: Clinician | None = None

    @classmethod
    def create(cls, config: AppConfig) -> AppContext:
        config.ensure_dirs()
        db = Database(config.db_path)
        repos = Repositories(db)
        # Load clinic-configurable clinical settings over the bootstrap defaults.
        _apply_settings(config, repos)
        # Ensure a media folder exists for each clinic-defined custom substance.
        from ..services import substances as _subs
        for key, _label in _subs.custom_substances(repos.settings):
            (config.media_root / key).mkdir(parents=True, exist_ok=True)
        return cls(
            config=config,
            db=db,
            repos=repos,
            auth=AuthService(repos.clinicians),
            crisis=CrisisService(repos.settings),
            media=MediaLibrary(config.media_root),
        )


def _apply_settings(config: AppConfig, repos: Repositories) -> None:
    s = repos.settings
    def as_int(key: str, current: int) -> int:
        val = s.get(key)
        try:
            return int(val) if val is not None else current
        except ValueError:
            return current

    def as_bool(key: str, current: bool) -> bool:
        val = s.get(key)
        return val == "1" if val is not None else current

    config.session_time_cap_seconds = as_int("time_cap_seconds", config.session_time_cap_seconds)
    config.periodic_vas_seconds = as_int("periodic_vas_seconds", config.periodic_vas_seconds)
    config.habituation_threshold = as_int("habituation_threshold", config.habituation_threshold)
    config.habituation_consecutive = as_int("habituation_consecutive", config.habituation_consecutive)
    config.autoscroll_on_grading = as_bool("autoscroll_on_grading", config.autoscroll_on_grading)
    config.autoscroll_timed_seconds = as_int("autoscroll_timed_seconds", config.autoscroll_timed_seconds)
    config.accessibility_kbmode = as_bool("accessibility_kbmode", config.accessibility_kbmode)
    config.vas_prompt_after_coping = as_bool("vas_prompt_after_coping", config.vas_prompt_after_coping)
    config.vas_prompt_every_n_cues = as_int("vas_prompt_every_n_cues", config.vas_prompt_every_n_cues)
    cue_audio = s.get("cue_audio_mode")
    if cue_audio in ("auto", "always", "muted", "audio_only"):
        config.cue_audio_mode = cue_audio
    config.pause_video_on_rating = as_bool("pause_video_on_rating", config.pause_video_on_rating)
    config.video_loop = as_bool("video_loop", config.video_loop)
    config.max_cue_exposure_sec = as_int("max_cue_exposure_sec", config.max_cue_exposure_sec)
    config.default_random_order = as_bool("default_random_order", config.default_random_order)
    config.default_loop = as_bool("default_loop", config.default_loop)
    config.default_start_fullscreen = as_bool("default_start_fullscreen", config.default_start_fullscreen)
    config.vas_prompt_per_cue_seconds = as_int("vas_prompt_per_cue_seconds", config.vas_prompt_per_cue_seconds)
    config.adaptive_ordering = as_bool("adaptive_ordering", config.adaptive_ordering)

    config.progressive_downreg_enabled = as_bool("progressive_downreg_enabled", config.progressive_downreg_enabled)
    lever = s.get("progressive_downreg_lever")
    if lever in ("blur", "shrink", "dim"):
        config.progressive_downreg_lever = lever
    config.progressive_downreg_target_pct = as_int("progressive_downreg_target_pct", config.progressive_downreg_target_pct)
    mode = s.get("progressive_downreg_mode")
    if mode in ("linear", "stepped"):
        config.progressive_downreg_mode = mode
    config.progressive_downreg_step_seconds = as_int("progressive_downreg_step_seconds", config.progressive_downreg_step_seconds)

    config.auto_coping_enabled = as_bool("auto_coping_enabled", config.auto_coping_enabled)
    config.auto_coping_threshold = as_int("auto_coping_threshold", config.auto_coping_threshold)
    config.auto_coping_consecutive = as_int("auto_coping_consecutive", config.auto_coping_consecutive)

    # Session mode and interspersed parameters.
    session_mode = s.get("default_session_mode")
    if session_mode in ("intense", "interspersed", "custom"):
        config.default_session_mode = session_mode
    config.interspersed_craving_pct = as_int("interspersed_craving_pct", config.interspersed_craving_pct)
    config.interspersed_craving_count = as_int("interspersed_craving_count", config.interspersed_craving_count)
    config.interspersed_min_exposure_sec = as_int("interspersed_min_exposure_sec", config.interspersed_min_exposure_sec)
    config.interspersed_vas_on_neutral = as_bool("interspersed_vas_on_neutral", config.interspersed_vas_on_neutral)
    config.interspersed_vas_delay_ms = as_int("interspersed_vas_delay_ms", config.interspersed_vas_delay_ms)

    # Video cue behaviour.
    config.video_wait_full_loop = as_bool("video_wait_full_loop", config.video_wait_full_loop)

    # Dynamic neutral increase.
    config.dynamic_neutral_enabled = as_bool("dynamic_neutral_enabled", config.dynamic_neutral_enabled)
    config.dynamic_neutral_threshold = as_int("dynamic_neutral_threshold", config.dynamic_neutral_threshold)

    # Min-exposure countdown hint.
    config.show_min_exposure_hint = as_bool("show_min_exposure_hint", config.show_min_exposure_hint)

    # Backlog rotation.
    config.max_cue_repeats = as_int("max_cue_repeats", config.max_cue_repeats)

    # VAS display mode.
    vas_display = s.get("vas_display_mode")
    if vas_display in ("slider", "circles", "stars"):
        config.vas_display_mode = vas_display

    # The clinic-selected UI language (persisted by the language switcher) overrides
    # the bootstrap default. app.main() applies it to i18n after the context is built.
    locale = s.get("locale")
    if locale:
        config.locale = locale
    theme = s.get("theme")
    if theme:
        config.theme = theme
