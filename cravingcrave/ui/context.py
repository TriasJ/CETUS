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
    # The clinic-selected UI language (persisted by the language switcher) overrides
    # the bootstrap default. app.main() applies it to i18n after the context is built.
    locale = s.get("locale")
    if locale:
        config.locale = locale
