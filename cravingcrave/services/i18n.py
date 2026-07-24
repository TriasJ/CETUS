"""Tiny i18n string table with runtime locale switching and auto-discovery.

UI code calls ``tr("some.key")`` and never hard-codes a language. Spanish (``es``)
is the default; English (``en``) ships complete. **Adding a language is a drop-in:**
create ``resources/i18n/<code>.json`` (copy ``es.json`` and translate) — include a
``"_language.name"`` key with the language's native name — and it appears
automatically in the in-app switcher. Optionally add ``resources/help/<code>.json``
for a translated manual.
"""

from __future__ import annotations

import json

from .. import paths

DEFAULT_LOCALE = "es"
# Key inside each locale file whose value is the language's own native display name.
_NAME_KEY = "_language.name"


class I18n:
    def __init__(self, locale: str = DEFAULT_LOCALE) -> None:
        self.locale = locale
        self._strings: dict[str, str] = {}
        self.load(locale)

    def load(self, locale: str) -> None:
        path = paths.resource_path("i18n", f"{locale}.json")
        with open(path, encoding="utf-8") as fh:
            self._strings = json.load(fh)
        self.locale = locale

    def tr(self, key: str, **kwargs) -> str:
        text = self._strings.get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                pass
        return text


_instance = I18n()


def tr(key: str, **kwargs) -> str:
    return _instance.tr(key, **kwargs)


def set_locale(locale: str) -> None:
    _instance.load(locale)


def current_locale() -> str:
    """The locale currently loaded in the shared instance."""
    return _instance.locale


def available_locales() -> list[tuple[str, str]]:
    """Discover shipped languages as ``(code, native_name)``, sorted with the default
    first. Reads every ``resources/i18n/*.json``; the display name comes from that
    file's ``_language.name`` (falling back to the code). Robust when frozen."""
    out: list[tuple[str, str]] = []
    i18n_dir = paths.resource_path("i18n")
    try:
        files = sorted(p for p in i18n_dir.glob("*.json"))
    except OSError:
        files = []
    for path in files:
        code = path.stem
        name = code
        try:
            with open(path, encoding="utf-8") as fh:
                name = json.load(fh).get(_NAME_KEY, code)
        except (OSError, ValueError):
            pass
        out.append((code, name))
    # Default locale first, then alphabetical by native name.
    out.sort(key=lambda cn: (cn[0] != DEFAULT_LOCALE, cn[1].lower()))
    return out or [(DEFAULT_LOCALE, "Español")]
