"""Dev-only: build a small, attribution-clean CC sample media set committed to git
so a fresh clone runs out-of-the-box. Copies chosen files to sample_* names and
writes a per-folder _SAMPLES.csv with attribution looked up from _licenses.csv.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "media"

SELECTION = {
    "alcohol": ["g07_oa_beer-glass_05.jpg", "g13_oa_bar-pub-interior-people_05.jpg",
                "g20_oa_nightclub-bar-night-drin_01.jpg"],
    "cigarettes": ["g09_oa_cigarette_03.jpg", "g01_oa_ashtray-cigarette_03.jpg",
                   "g06_oa_cigarette_01.jpg"],
    "positive": ["oa_puppy-dog_01.jpg", "oa_puppy-dog_03.jpg", "oa_puppy-dog_04.jpg"],
    "sounds": ["fs_pouring-beer-into-glass_01.mp3", "fs_bar-pub-ambience-crowd_03.mp3",
               "fs_cigarette-lighter-flick_01.mp3"],
}


def _load_licenses(folder: Path) -> dict[str, dict]:
    f = folder / "_licenses.csv"
    if not f.exists():
        return {}
    rows = {}
    with f.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows[row["file"]] = row
    return rows


def main() -> None:
    total = 0
    for cat, files in SELECTION.items():
        folder = MEDIA / cat
        lic = _load_licenses(folder)
        out_rows = []
        # clear any prior samples so this is idempotent
        for old in folder.glob("sample_*"):
            old.unlink()
        for name in files:
            src = folder / name
            if not src.is_file():
                print(f"  ! missing {src}")
                continue
            dest = folder / f"sample_{name}"
            shutil.copy2(src, dest)
            stem = Path(name).stem
            row = lic.get(stem, {})
            out_rows.append({
                "file": dest.name,
                "license": row.get("license", ""),
                "creator": row.get("creator", ""),
                "source_url": row.get("source_url", ""),
            })
            total += 1
            print(f"  [ok] {cat}/{dest.name}")
        with (folder / "_SAMPLES.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["file", "license", "creator", "source_url"])
            w.writeheader(); w.writerows(out_rows)
    print(f"\nWrote {total} sample files + _SAMPLES.csv per folder.")


if __name__ == "__main__":
    main()
