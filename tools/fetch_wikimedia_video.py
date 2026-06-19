"""Download Creative-Commons / public-domain VIDEO from Wikimedia Commons.

Wikimedia Commons (https://commons.wikimedia.org) is a large repository of freely
licensed video (CC0 / CC-BY / CC-BY-SA / public domain). No API key required.

Each clip is downloaded and re-encoded to the app's safe playback profile
(H.264 + AAC mp4, <=720p) using ffmpeg. ffmpeg is taken from the bundled
``imageio-ffmpeg`` package if installed, else from PATH.

Examples:
    python tools/fetch_wikimedia_video.py --query "beer pouring glass" --category alcohol --count 2
    python tools/fetch_wikimedia_video.py --query "cigarette smoking" --category cigarettes --count 2
    python tools/fetch_wikimedia_video.py --query "forest stream nature" --category positive --count 2

Wikimedia content usually requires attribution (logged to _licenses.csv). Confirm
each clip's license and clinical appropriateness before use with patients.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia asks for a descriptive User-Agent identifying the tool.
USER_AGENT = "CETUS-ContentTool/0.1 (clinical CET media tool; non-commercial)"
CATEGORIES = ("alcohol", "cigarettes", "meth", "positive", "sounds")
_TAGS = re.compile(r"<[^>]+>")


def ffmpeg_exe() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg")


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str, dest: Path) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as exc:
        print(f"  ! download failed: {exc}")
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch CC video from Wikimedia Commons -> media/<category>.")
    ap.add_argument("--query", required=True)
    ap.add_argument("--category", required=True, choices=CATEGORIES)
    ap.add_argument("--count", type=int, default=2)
    ap.add_argument("--media-root", default="media")
    ap.add_argument("--max-seconds", type=int, default=20, help="trim each clip to N seconds")
    args = ap.parse_args()

    ff = ffmpeg_exe()
    if not ff:
        sys.exit("ffmpeg not found. Run: pip install imageio-ffmpeg")

    out_dir = Path(args.media_root) / args.category
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() else "-" for c in args.query.lower())[:24].strip("-")

    params = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{args.query} filetype:video", "gsrnamespace": 6,
        "gsrlimit": min(args.count * 3, 30),
        "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata",
    })
    print(f"Searching Wikimedia Commons for video: {args.query!r}")
    data = _get_json(f"{API}?{params}")
    pages = list((data.get("query") or {}).get("pages", {}).values())

    rows, saved = [], 0
    for page in pages:
        if saved >= args.count:
            break
        info = (page.get("imageinfo") or [{}])[0]
        mime = info.get("mime", "")
        src_url = info.get("url")
        if not src_url or not mime.startswith("video/"):
            continue
        meta = info.get("extmetadata", {})
        license_name = (meta.get("LicenseShortName", {}) or {}).get("value", "")
        artist = _TAGS.sub("", (meta.get("Artist", {}) or {}).get("value", "")).strip()

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / Path(urllib.parse.urlparse(src_url).path).name
            print(f"  downloading {page.get('title', '')}  ({license_name})")
            if not _download(src_url, raw):
                continue
            dest = out_dir / f"wm_{slug}_{saved + 1:02d}.mp4"
            cmd = [ff, "-y", "-i", str(raw), "-t", str(args.max_seconds),
                   "-vf", "scale=-2:'min(720,ih)'", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-movflags", "+faststart", str(dest)]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
            except subprocess.CalledProcessError as exc:
                print(f"  ! transcode failed: {exc.stderr.decode('utf-8', 'replace')[-200:]}")
                continue
            saved += 1
            rows.append([dest.stem, license_name, artist, src_url])
            print(f"  [ok] {dest.name}")

    if rows:
        lic = out_dir / "_licenses.csv"
        write_header = not lic.exists()
        with open(lic, "a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if write_header:
                w.writerow(["file", "license", "creator", "source_url"])
            w.writerows(rows)
    print(f"\nDone. Saved {saved} clip(s) to {out_dir}. Review license + appropriateness before use.")


if __name__ == "__main__":
    main()
