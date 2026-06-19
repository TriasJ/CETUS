"""Clinician authentication. Local-only, no cloud.

Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes, never plaintext. This
gates the clinician dashboard; it is not a security boundary against a determined
local attacker (the SQLite file is on the same machine) but prevents casual
shoulder access to patient data.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Optional

from .. import config
from ..domain.models import Clinician
from ..data.repositories import ClinicianRepo, SettingRepo

_ITERATIONS = 200_000
ADMIN_KEY_SETTING = "admin_key_hash"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


class AuthService:
    def __init__(self, clinicians: ClinicianRepo) -> None:
        self.clinicians = clinicians

    def has_any_clinician(self) -> bool:
        return self.clinicians.count() > 0

    def register(self, username: str, display_name: str, password: str) -> Clinician:
        return self.clinicians.create(
            Clinician(
                username=username.strip(),
                display_name=display_name.strip() or username.strip(),
                password_hash=hash_password(password),
            )
        )

    def login(self, username: str, password: str) -> Optional[Clinician]:
        clinician = self.clinicians.get_by_username(username.strip())
        if clinician and verify_password(password, clinician.password_hash):
            return clinician
        return None

    def list_clinicians(self) -> list[Clinician]:
        return self.clinicians.list_all()

    def reset_password(self, clinician_id: int, new_password: str) -> None:
        self.clinicians.update_password(clinician_id, hash_password(new_password))


# --- Admin recovery key (gates the in-app debug/recovery dialog) -------------
# Local-only app: filesystem access to the DB is the real trust boundary, so this
# key just keeps the recovery dialog non-trivial for a casual user at a clinic
# kiosk. Stored hashed in app_setting; until a clinic sets its own, a documented
# default applies so a locked-out clinician can always recover.

def verify_admin_key(settings: SettingRepo, key: str) -> bool:
    stored = settings.get(ADMIN_KEY_SETTING)
    if stored:
        return verify_password(key, stored)
    return key == config.DEFAULT_ADMIN_KEY


def admin_key_is_default(settings: SettingRepo) -> bool:
    """True when no custom admin key has been set (the default is still active)."""
    return settings.get(ADMIN_KEY_SETTING) is None


def set_admin_key(settings: SettingRepo, key: str) -> None:
    settings.set(ADMIN_KEY_SETTING, hash_password(key))
