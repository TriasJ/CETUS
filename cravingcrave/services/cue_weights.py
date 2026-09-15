"""Lookup service for empirically-derived cue craving weights.

The bundled JSON files in ``resources/cue_weights/`` contain pre-assigned
craving weights from validated research datasets (MOCIS for meth/opioid,
Tobacco dataset for cigarettes).  These weights serve as research-backed
defaults for the ``craving_weight`` field on ``CueConfig``.

The MOCIS dataset reuses ``Slide{NNN}.jpeg`` filenames across its three image
sets (control, meth, opioid), so the lookup is keyed by ``image_set/file`` and
the caller supplies the substance folder from the media path.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .. import paths

# Maps CETUS substance/folder names to MOCIS image_set identifiers.
_FOLDER_TO_SET: dict[str, str] = {
    "neutral": "control",
    "meth": "meth",
    "opioid": "opioid",
}


@lru_cache(maxsize=1)
def _load_meth_opi() -> dict[str, float]:
    """Load MOCIS weights: {image_set/filename_lower: craving_weight_0_10}."""
    p = paths.resource_path("cue_weights", "meth_opi_weights.json")
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {
        f'{e["image_set"]}/{e["file"].lower()}': e["craving_weight"]
        for e in data.get("entries", [])
        if "file" in e and "craving_weight" in e and "image_set" in e
    }


class CueWeightLookup:
    """Suggest a craving weight for a cue based on its media path."""

    def __init__(self) -> None:
        self._meth_opi = _load_meth_opi()

    def suggest(self, media_path: str) -> float | None:
        """Return the published craving weight (0-10) for a media file, or None.

        *media_path* is the CETUS relative path, e.g. ``"meth/gen_crystal_01.png"``
        or ``"neutral/mocis_mmc1_p005_1.png"``.  The folder name is used to select
        the correct image set in the MOCIS data.
        """
        parts = Path(media_path).parts
        if len(parts) < 2:
            return None
        folder = parts[0].lower()
        filename = parts[-1].lower()
        image_set = _FOLDER_TO_SET.get(folder)
        if image_set:
            key = f"{image_set}/{filename}"
            w = self._meth_opi.get(key)
            if w is not None:
                return w
        # Fallback: try all image sets (for files whose folder doesn't map).
        for s in ("control", "meth", "opioid"):
            w = self._meth_opi.get(f"{s}/{filename}")
            if w is not None:
                return w
        return None

    def available(self) -> bool:
        """True if any weight data is loaded."""
        return bool(self._meth_opi)
