"""Dev-only: apply a default appetitive-intensity grade to the starter library.

Renames each file to ``gNN_<original>`` (NN = rank, low->high appetitive intensity)
so the app — which orders cues by filename — adds them in graded escalation order.
Also rewrites each folder's ``_licenses.csv`` so attribution stays linked.

Idempotent: files already prefixed with ``gNN_`` are skipped.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Ordered low -> high appetitive intensity (distal/contextual -> proximal/consummatory).
ORDER = {
    "alcohol": [
        "oa_wine-bottle-bar_05.jpg",  # retail shelf (distal)
        "oa_wine-bottle-bar_01.jpg",  # back-bar bottles
        "oa_wine-bottle-bar_04.jpg",  # green bottles
        "oa_wine-bottle-bar_02.jpg",  # bar atmosphere
        "oa_wine-bottle-bar_03.jpg",  # spirit bottles (product)
        "oa_beer-glass_03.jpg",       # amber beer on table
        "oa_beer-glass_05.jpg",       # two pale beers
        "oa_beer-glass_04.jpg",       # beers with snacks (social)
        "oa_beer-glass_01.jpg",       # frosty beer outdoors
        "oa_beer-glass_02.jpg",       # beer stein close-up (consummatory)
        # evocative environments (social context, high real-world trigger value):
        "oa_bar-pub-interior-people_04.jpg",  # quiet wooden pub
        "oa_bar-pub-interior-people_01.jpg",  # warm pub
        "oa_bar-pub-interior-people_05.jpg",  # dim bar
        "oa_bar-pub-interior-people_02.jpg",  # bar lounge
        "oa_pub-beer-taps-bartender_03.jpg",  # long bar
        "oa_pub-beer-taps-bartender_01.jpg",  # bartender
        "oa_pub-beer-taps-bartender_02.jpg",  # pint on the bar (proximal in context)
        "oa_bar-pub-interior-people_03.jpg",  # nightclub crowd
        "oa_nightclub-bar-night-drin_04.jpg", # neon bar at night
        "oa_nightclub-bar-night-drin_01.jpg", # club
        "oa_nightclub-bar-night-drin_03.jpg", # club crowd
        "oa_nightclub-bar-night-drin_02.jpg", # nightlife / DJ (high arousal)
    ],
    "cigarettes": [
        "oa_ashtray-cigarette_03.jpg",  # ash close-up (aftermath/aversive)
        "oa_ashtray-cigarette_01.jpg",  # butts
        "oa_ashtray-cigarette_02.jpg",  # case of butts
        "oa_ashtray-cigarette_04.jpg",  # vintage person (context)
        "oa_cigarette_02.jpg",          # person
        "oa_cigarette_01.jpg",          # person
        "oa_cigarette_04.jpg",          # social scene
        "oa_cigarette_05.jpg",          # pile of fresh cigarettes
        "oa_cigarette_03.jpg",          # single clean cigarette
        # evocative active-use / availability cues:
        "oa_lit-cigarette-close-up_01.jpg",   # lighter flame (pre-use)
        "oa_lit-cigarette-close-up_02.jpg",   # lighter
        "oa_lit-cigarette-close-up_04.jpg",   # lighter spark
        "oa_person-smoking-cigarette_04.jpg", # street/person (context)
        "oa_person-smoking-cigarette_03.jpg", # portrait
        "oa_person-smoking-cigarette_05.jpg", # cigarette pack (availability)
        "oa_woman-smoking-cigarette_01.webp", # person smoking (active)
        "oa_person-smoking-cigarette_01.webp",# hand holding cigarette
        "oa_lit-cigarette-close-up_03.jpg",   # lit cigarette in hand, smoke (consummatory)
    ],
    # AI-generated cues (Gemini): paraphernalia -> acquisition -> ready substance ->
    # active use (smoke). Smoke/active-use cues are the most proximal/consummatory.
    "meth": [
        "gen_a-clear-glass-pipe-resti_01.png",   # empty glass pipe (paraphernalia)
        "gen_a-clear-glass-pipe-resti_02.png",   # glass pipe
        "gen_small-clear-crystals-ins_01.png",   # crystals in a bag (acquisition)
        "gen_small-clear-crystals-ins_02.png",   # crystals in a bag
        "gen_meth_01.png",                       # crystals on foil (ready)
        "gen_macro-photo-of-clear-cry_01.png",   # crystals close-up
        "gen_macro-photo-of-clear-cry_02.png",   # crystals close-up
        "gen_wisps-of-white-smoke-ris_01.png",   # pipe + smoke on table (active use)
        "gen_wisps-of-white-smoke-ris_02.png",   # pipe + smoke on table
        "gen_thick-white-smoke-fillin_01.png",   # pipe filled with smoke
        "gen_thick-white-smoke-fillin_02.png",   # smoke (ambiguous; review)
        "gen_white-vapor-swirling-abo_01.png",   # hand holding pipe, vapor
        "gen_white-vapor-swirling-abo_02.png",   # hand holding pipe, vapor (most proximal)
    ],
}


def main() -> None:
    for category, names in ORDER.items():
        folder = ROOT / "media" / category
        mapping: dict[str, str] = {}  # old stem -> new stem
        for rank, name in enumerate(names, start=1):
            src = folder / name
            if not src.exists():
                print(f"  skip (missing/already graded): {name}")
                continue
            new_name = f"g{rank:02d}_{name}"
            src.rename(folder / new_name)
            mapping[Path(name).stem] = Path(new_name).stem
            print(f"  {name} -> {new_name}")

        lic = folder / "_licenses.csv"
        if lic.exists() and mapping:
            rows = list(csv.reader(lic.open(encoding="utf-8")))
            for r in rows[1:]:
                if r and r[0] in mapping:
                    r[0] = mapping[r[0]]
            with lic.open("w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerows(rows)
        print(f"[{category}] graded {len(mapping)} files.\n")


if __name__ == "__main__":
    main()
