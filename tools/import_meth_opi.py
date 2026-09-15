"""Extract cue images from METH/OPI supplementary PDFs and sort by category.

Requires: pip install pymupdf

The MOCIS (Meth/Opioid Craving Image Set) publishes its cue images as
supplementary PDF files (mmc1, mmc3-mmc5).  This script extracts the embedded
images and files them into media/{meth,opioid,neutral}/ based on the CSV
category mapping from mmc2.

Usage:
    pip install pymupdf
    python tools/import_meth_opi.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "Módulo 5" / "METH AND OPI"
CSV_PATH = DOCS / "1-s2.0-S037687162030106X-mmc2.csv"
MEDIA = ROOT / "media"

# Supplementary PDFs containing the actual cue images.
PDFS = [
    DOCS / "1-s2.0-S037687162030106X-mmc1.pdf",
    DOCS / "1-s2.0-S037687162030106X-mmc3.pdf",
    DOCS / "1-s2.0-S037687162030106X-mmc4.pdf",
    DOCS / "1-s2.0-S037687162030106X-mmc5.pdf",
]

# Map CSV categories to media folders.
CATEGORY_MAP: dict[str, str] = {
    # Control/neutral categories -> media/neutral/
    "control_objects": "neutral",
    "control_objects_hand": "neutral",
    "control_tool": "neutral",
    "control_tool_face": "neutral",
    "control_tool_hand_complex": "neutral",
    "control_tool_hand_simple": "neutral",
    # Meth categories -> media/meth/
    "meth": "meth",
    "meth_face_activities": "meth",
    "meth_hand": "meth",
    "meth_injection_hand": "meth",
    "meth_instrument": "meth",
    "meth_instrument_hand": "meth",
    # Opioid categories -> media/opioid/
    "opioid": "opioid",
    "opioid_face_activities": "opioid",
    "opioid_hand": "opioid",
    "opioid_injection_hand": "opioid",
    "opioid_injection_instrument": "opioid",
    "opioid_instrument_hand": "opioid",
}

# Minimum image size in bytes — skip tiny decorations / icons.
MIN_IMAGE_BYTES = 5_000


def load_csv_metadata() -> dict[str, dict]:
    """Load the CSV and return {filename: {category, folder, craving_mean, ...}}."""
    if not CSV_PATH.exists():
        print(f"CSV not found: {CSV_PATH}")
        return {}
    meta: dict[str, dict] = {}
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            filename = row.get("File", "").strip()
            if not filename:
                continue
            category = row.get("Category", "").strip()
            craving = row.get("allsubjects_craving_mean", "0")
            arousal = row.get("allsubjects_arousal_mean", "0")
            valence = row.get("allsubjects_valence_mean", "0")
            meta[filename] = {
                "category": category,
                "folder": CATEGORY_MAP.get(category, "neutral"),
                "craving_mean": float(craving) if craving else 0.0,
                "arousal_mean": float(arousal) if arousal else 0.0,
                "valence_mean": float(valence) if valence else 0.0,
            }
    return meta


def extract_images_from_pdfs() -> None:
    """Extract images from each PDF using pymupdf."""
    try:
        import fitz  # noqa: F401 — pymupdf
    except ImportError:
        print("pymupdf not installed.  Run:  pip install pymupdf")
        sys.exit(1)

    meta = load_csv_metadata()

    # Ensure target directories exist.
    for folder in ("meth", "opioid", "neutral"):
        (MEDIA / folder).mkdir(parents=True, exist_ok=True)

    total = 0
    for pdf_path in PDFS:
        if not pdf_path.exists():
            print(f"  PDF not found, skipping: {pdf_path.name}")
            continue

        print(f"\nProcessing {pdf_path.name} ...")
        doc = fitz.open(str(pdf_path))

        for page_num in range(len(doc)):
            page = doc[page_num]
            images = page.get_images(full=True)

            for img_idx, img in enumerate(images):
                xref = img[0]
                base_image = doc.extract_image(xref)
                if base_image is None:
                    continue

                ext = base_image.get("ext", "png")
                img_bytes = base_image["image"]

                if len(img_bytes) < MIN_IMAGE_BYTES:
                    continue

                # Derive a stable filename from the PDF and page number.
                pdf_tag = pdf_path.stem.split("-")[-1]          # mmc1, mmc3, …
                name = f"mocis_{pdf_tag}_p{page_num + 1:03d}_{img_idx + 1}.{ext}"

                # Match the page to a CSV row (CSV uses "Slide{NNN}.jpeg").
                slide_name = f"Slide{page_num + 1:03d}.jpeg"
                info = meta.get(slide_name, {})
                folder = info.get("folder", "neutral")

                dest = MEDIA / folder / name
                if dest.exists():
                    continue

                dest.write_bytes(img_bytes)
                total += 1

        doc.close()
        print(f"  {pdf_path.name}: done")

    print(f"\nExtracted {total} images total.")


def main() -> None:
    print("METH/OPI Image Extractor (MOCIS)")
    print("=" * 40)
    extract_images_from_pdfs()


if __name__ == "__main__":
    main()
