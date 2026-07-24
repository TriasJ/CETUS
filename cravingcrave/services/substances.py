"""Substance registry: 3 locked built-ins + clinic-defined custom substances.

Custom substances are persisted in ``app_setting`` under key ``custom_substances``
as a JSON list of ``{"key","label"}``. The key is a filesystem/DB-safe slug derived
from the label; the label is shown verbatim (built-ins resolve via i18n instead).

Removing a custom substance only *hides* it (drops it from the JSON list) — existing
patient/session/cue rows that reference its key are never touched, so historical data
and reports stay intact.
"""

from __future__ import annotations

import json
import re
import unicodedata

from ..data.repositories import SettingRepo
from .i18n import tr

BUILTIN_KEYS = ("alcohol", "cigarettes", "meth")
SETTING_KEY = "custom_substances"


def slugify(label: str) -> str:
    """ASCII, lowercase, hyphenated slug safe for folder names and DB values."""
    norm = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode("ascii")
    norm = re.sub(r"[^a-zA-Z0-9]+", "-", norm).strip("-").lower()
    return norm


def _load_custom(settings: SettingRepo) -> list[dict]:
    raw = settings.get(SETTING_KEY)
    if not raw:
        return []
    try:
        items = json.loads(raw)
        return [i for i in items if isinstance(i, dict) and i.get("key") and i.get("label")]
    except (ValueError, TypeError):
        return []


def custom_substances(settings: SettingRepo) -> list[tuple[str, str]]:
    """Clinic-defined substances as (key, label), in insertion order."""
    return [(i["key"], i["label"]) for i in _load_custom(settings)]


def available_substances(settings: SettingRepo) -> list[tuple[str, str]]:
    """All selectable substances as (key, display_label): built-ins first, then custom."""
    out = [(k, tr(f"substance.{k}")) for k in BUILTIN_KEYS]
    out.extend(custom_substances(settings))
    return out


def display_name(settings: SettingRepo, key: str) -> str:
    """Display label for any substance key (built-in via i18n, custom via stored label,
    unknown/legacy key shown verbatim so old data never renders blank)."""
    if key in BUILTIN_KEYS:
        return tr(f"substance.{key}")
    for k, label in custom_substances(settings):
        if k == key:
            return label
    return key


def add_custom(settings: SettingRepo, label: str) -> str | None:
    """Add a custom substance from a free-text label. Returns its key, or None if the
    label is empty/duplicate/collides with a built-in."""
    label = label.strip()
    key = slugify(label)
    if not key or key in BUILTIN_KEYS:
        return None
    items = _load_custom(settings)
    if any(i["key"] == key for i in items):
        return None
    items.append({"key": key, "label": label})
    settings.set(SETTING_KEY, json.dumps(items, ensure_ascii=False))
    return key


def hide_custom(settings: SettingRepo, key: str) -> None:
    """Remove a custom substance from the selectable list (data is NOT deleted)."""
    items = [i for i in _load_custom(settings) if i["key"] != key]
    settings.set(SETTING_KEY, json.dumps(items, ensure_ascii=False))
