"""Loads the in-app help/manual content (HTML topics) from resources."""

from __future__ import annotations

import json

from .. import paths


def load_help(locale: str = "es") -> dict:
    """Return {'title': str, 'sections': [{'id','title','html'}, ...]}."""
    path = paths.resource_path("help", f"{locale}.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
