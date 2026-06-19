"""Tiny i18n string table.

Spanish (``es``) is the only locale shipped; an ``en`` skeleton proves the
mechanism so strings stay centralized and clinically reviewable. UI code calls
``tr("some.key")`` and never hard-codes Spanish.
"""

from __future__ import annotations

import json

from .. import paths


class I18n:
    def __init__(self, locale: str = "es") -> None:
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
