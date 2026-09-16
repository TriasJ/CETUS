"""Copy neutral control images from the Tobacco dataset to media/neutral/.

Images 110-224 in docs/Módulo 5/Tabaco/Data/ are neutral (non-cigarette) images
from a validated research set (Zheng et al., 2021).  They serve as non-craving
control stimuli for the Interspersed Neutral session mode.

Usage:
    python tools/import_tobacco_neutrals.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

# Resolve project root from this script's location.
ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "Módulo 5" / "Tabaco" / "Data"
DEST = ROOT / "media" / "neutral"
NEUTRAL_RANGE = range(110, 225)  # images 110-224 are neutral controls


def main() -> None:
    if not SOURCE.is_dir():
        print(f"Source directory not found: {SOURCE}")
        sys.exit(1)

    DEST.mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped = 0
    missing = 0
    for n in NEUTRAL_RANGE:
        # Handle filename quirks: some have trailing spaces or mixed-case extensions.
        candidates = [
            SOURCE / f"{n}.jpg",
            SOURCE / f"{n}.JPG",
            SOURCE / f"{n}.jpeg",
            SOURCE / f"{n} .jpg",   # e.g. "112 .jpg", "172 .jpg"
            SOURCE / f"{n} .JPG",
        ]
        src = None
        for c in candidates:
            if c.exists():
                src = c
                break
        if src is None:
            missing += 1
            continue
        dest_name = f"tobacco_neutral_{n:03d}.jpg"
        dest_path = DEST / dest_name
        if dest_path.exists():
            skipped += 1
            continue
        shutil.copy2(src, dest_path)
        copied += 1

    print(f"Imported {copied} neutral images to {DEST}")
    if skipped:
        print(f"  Skipped {skipped} (already present)")
    if missing:
        print(f"  Missing {missing} source images (not in dataset)")


if __name__ == "__main__":
    main()
