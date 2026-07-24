"""Loads the in-app help/manual content (HTML topics) from resources."""

from __future__ import annotations

import json

from .. import paths
from .i18n import DEFAULT_LOCALE


def load_help(locale: str = DEFAULT_LOCALE) -> dict:
    """Return {'title': str, 'sections': [{'id','title','html'}, ...]}.

    Falls back to the default-locale manual if a translated help file for ``locale``
    is not shipped, so a new UI language never yields an empty Help window."""
    path = paths.resource_path("help", f"{locale}.json")
    if not path.is_file():
        path = paths.resource_path("help", f"{DEFAULT_LOCALE}.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
