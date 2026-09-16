"""Generate cue weight JSON from the METH/OPI CSV dataset.

Reads the rating data from the MOCIS CSV and produces a bundled JSON
file at cravingcrave/resources/cue_weights/meth_opi_weights.json for
use by the CueWeightLookup service.

Craving scores in the CSV are on a 0-100 VAS.  The ``craving_weight`` field
normalises them to 0-10 so they align with CETUS' clinical VAS scale.

Usage:
    python tools/gen_cue_weights.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "docs" / "Módulo 5" / "METH AND OPI" / "1-s2.0-S037687162030106X-mmc2.csv"
OUT_DIR = ROOT / "cravingcrave" / "resources" / "cue_weights"
OUT_PATH = OUT_DIR / "meth_opi_weights.json"


def main() -> None:
    if not CSV_PATH.exists():
        print(f"CSV not found: {CSV_PATH}")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            filename = row.get("File", "").strip()
            category = row.get("Category", "").strip()
            image_set = row.get("ImageSet", "").strip()
            craving = float(row.get("allsubjects_craving_mean", "0") or "0")
            arousal = float(row.get("allsubjects_arousal_mean", "0") or "0")
            valence = float(row.get("allsubjects_valence_mean", "0") or "0")
            typicality = float(row.get("allsubjects_typicality_mean", "0") or "0")

            entries.append({
                "file": filename,
                "image_set": image_set,
                "category": category,
                "craving_mean_100": round(craving, 2),
                "craving_weight": round(craving / 10.0, 3),   # normalise to 0-10
                "arousal_mean": round(arousal, 2),
                "valence_mean": round(valence, 2),
                "typicality_mean": round(typicality, 2),
            })

    data = {
        "source": "Meth/Opioid Craving Image Set (MOCIS)",
        "scale": "craving_mean_100 is 0-100 VAS; craving_weight is normalised to 0-10",
        "n": len(entries),
        "entries": entries,
    }

    OUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(entries)} entries to {OUT_PATH}")


if __name__ == "__main__":
    main()
