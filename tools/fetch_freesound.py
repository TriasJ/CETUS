"""Download Creative-Commons sounds from Freesound into media/sounds (or any category).

Freesound (https://freesound.org) indexes large amounts of CC0 / CC-BY audio.
Requires a free API key in the FREESOUND_API_KEY environment variable
(get one at https://freesound.org/apiv2/apply/). Standard-library only.

Downloads the high-quality MP3 *preview* of each result (sufficient for ambient
beds and cue sounds) and logs license + attribution to _licenses.csv.

Examples:
    set FREESOUND_API_KEY=...
    python tools/fetch_freesound.py --query "bar restaurant ambience" --count 4
    python tools/fetch_freesound.py --query "pouring beer glass" --count 3
    python tools/fetch_freesound.py --query "lighter flick cigarette" --count 3
    python tools/fetch_freesound.py --query "forest birds calm" --category positive --count 3

Only CC0 and Attribution-licensed results are fetched. Review each clip and confirm
licensing/appropriateness before clinical use.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

API = "https://freesound.org/apiv2/search/text/"
USER_AGENT = "CETUS-ContentTool/0.1 (clinical CET media; respectful use)"
# CC0 + Attribution only (safest for clinical reuse).
LICENSE_FILTER = 'license:("Creative Commons 0" OR "Attribution")'


def _get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Authorization": f"Token {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str, dest: Path) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            dest.write_bytes(resp.read())
            return True
    except Exception as exc:
        print(f"  ! skip {url}: {exc}")
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch CC sounds from Freesound into media/<category>.")
    ap.add_argument("--query", required=True)
    ap.add_argument("--category", default="sounds")
    ap.add_argument("--count", type=int, default=4)
    ap.add_argument("--media-root", default="media")
    args = ap.parse_args()

    token = os.environ.get("FREESOUND_API_KEY")
    if not token:
        sys.exit("FREESOUND_API_KEY is not set. Get a key at https://freesound.org/apiv2/apply/")

    out_dir = Path(args.media_root) / args.category
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() else "-" for c in args.query.lower())[:24].strip("-")

    params = urllib.parse.urlencode({
        "query": args.query,
        "filter": LICENSE_FILTER,
        "fields": "id,name,license,username,url,previews",
        "page_size": min(args.count, 50),
    })
    print(f"Searching Freesound for: {args.query!r}")
    data = _get_json(f"{API}?{params}", token)
    results = data.get("results", [])[: args.count]
    if not results:
        print("No CC results.")
        return

    rows, saved = [], 0
    for i, item in enumerate(results, start=1):
        preview = (item.get("previews") or {}).get("preview-hq-mp3")
        if not preview:
            continue
        dest = out_dir / f"fs_{slug}_{i:02d}.mp3"
        if _download(preview, dest):
            saved += 1
            rows.append([dest.stem, item.get("license", ""), item.get("username", ""),
                         item.get("url", "")])
            print(f"  [ok] {dest.name}  ({item.get('license', '?')})")

    if rows:
        lic = out_dir / "_licenses.csv"
        write_header = not lic.exists()
        with open(lic, "a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if write_header:
                w.writerow(["file", "license", "creator", "source_url"])
            w.writerows(rows)
    print(f"\nDone. Saved {saved} sound(s) to {out_dir}. Review before clinical use.")


if __name__ == "__main__":
    main()
