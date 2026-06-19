"""Resolves the configurable safety contact numbers shown on the calm/panic screen.

Reads from ``app_setting`` (clinic-configurable) and falls back to the defaults in
``config``. These must always resolve to *something* so the panic screen is never
blank.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import config
from ..data.repositories import SettingRepo

KEY_THERAPIST = "therapist_phone"
KEY_CRISIS = "crisis_line"
KEY_EMERGENCY = "emergency_number"


@dataclass
class CrisisInfo:
    therapist_phone: str
    crisis_line: str
    emergency_number: str


class CrisisService:
    def __init__(self, settings: SettingRepo) -> None:
        self.settings = settings

    def get(self) -> CrisisInfo:
        return CrisisInfo(
            therapist_phone=self.settings.get(KEY_THERAPIST, config.DEFAULT_THERAPIST_PHONE),
            crisis_line=self.settings.get(KEY_CRISIS, config.DEFAULT_CRISIS_LINE),
            emergency_number=self.settings.get(KEY_EMERGENCY, config.DEFAULT_EMERGENCY_NUMBER),
        )

    def save(self, info: CrisisInfo) -> None:
        self.settings.set(KEY_THERAPIST, info.therapist_phone)
        self.settings.set(KEY_CRISIS, info.crisis_line)
        self.settings.set(KEY_EMERGENCY, info.emergency_number)
