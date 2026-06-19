"""Download Creative-Commons / open-access images into the media library.

Uses the Openverse API (https://openverse.org), which indexes CC-licensed and
public-domain images. Standard-library only — no pip install required.

Examples:
    python tools/fetch_open_access.py --query "beer glass bar" --category alcohol --count 8
    python tools/fetch_open_access.py --query "puppy golden retriever" --category positive --count 10
    python tools/fetch_open_access.py --query "forest waterfall" --category positive

Always review downloaded images for clinical appropriateness before use. License
metadata for each file is written to a sidecar ``_licenses.csv`` in the category
folder for your records.
"""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# Windows consoles default to cp1252; force UTF-8 so non-ASCII output never crashes.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

API = "https://api.openverse.org/v1/images/"
USER_AGENT = "CETUS-ContentTool/0.1 (clinical CET media; respectful use)"
CATEGORIES = ("alcohol", "cigarettes", "meth", "positive", "sounds")


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str, dest: Path) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
            ext = mimetypes.guess_extension(resp.headers.get_content_type() or "") or ".jpg"
            dest = dest.with_suffix(ext if ext != ".jpe" else ".jpg")
            dest.write_bytes(data)
            return True
    except Exception as exc:  # network / 404 / etc.
        print(f"  ! skip {url}: {exc}")
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch CC/open-access images into media/<category>.")
    ap.add_argument("--query", required=True, help="search terms")
    ap.add_argument("--category", required=True, choices=CATEGORIES)
    ap.add_argument("--count", type=int, default=8)
    ap.add_argument("--media-root", default="media", help="path to the media/ folder")
    args = ap.parse_args()

    out_dir = Path(args.media_root) / args.category
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() else "-" for c in args.query.lower())[:24].strip("-")

    params = urllib.parse.urlencode({
        "q": args.query,
        "page_size": min(args.count, 50),
        # commercial + modification keeps options broad while staying CC/PD.
        "license_type": "commercial,modification",
    })
    print(f"Searching Openverse for: {args.query!r}")
    data = _get_json(f"{API}?{params}")
    results = data.get("results", [])[: args.count]
    if not results:
        print("No results.")
        return

    rows = []
    saved = 0
    for i, item in enumerate(results, start=1):
        url = item.get("url")
        if not url:
            continue
        dest = out_dir / f"oa_{slug}_{i:02d}"
        if _download(url, dest):
            saved += 1
            rows.append([dest.name, item.get("license", ""), item.get("license_version", ""),
                         item.get("creator", ""), item.get("foreign_landing_url", "")])
            print(f"  [ok] {dest.name}  ({item.get('license', '?')})")

    if rows:
        lic = out_dir / "_licenses.csv"
        write_header = not lic.exists()
        with open(lic, "a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if write_header:
                w.writerow(["file", "license", "version", "creator", "source_url"])
            w.writerows(rows)
    print(f"\nDone. Saved {saved} image(s) to {out_dir}. Licenses logged to _licenses.csv.")
    print("Review each image for clinical appropriateness before using with patients.")


if __name__ == "__main__":
    main()
