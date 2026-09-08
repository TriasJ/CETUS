"""Download stock photos and videos from Pexels into the media library.

Uses the Pexels API (https://www.pexels.com/api/). Standard-library only — no
pip install required beyond Python 3.11+.

Examples:
    python tools/fetch_pexels.py --query "beer glass bar" --category alcohol --count 8
    python tools/fetch_pexels.py --query "bar scene party" --category alcohol --count 4 --type video
    python tools/fetch_pexels.py --query "puppy golden retriever" --category positive --orientation landscape
    python tools/fetch_pexels.py --query "cigarette smoking" --category cigarettes --size original

The Pexels License permits free commercial and research use.  API users MUST
credit the photographer: "Photo by [Name] on Pexels".  License metadata for
each file is written to a sidecar ``_licenses.csv`` in the category folder.

Always review downloaded media for clinical appropriateness before use.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Windows consoles default to cp1252; force UTF-8 so non-ASCII output never crashes.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

PHOTO_API = "https://api.pexels.com/v1/search"
VIDEO_API = "https://api.pexels.com/v1/videos/search"
USER_AGENT = "CETUS-ContentTool/0.1 (clinical CET media; respectful use)"
CATEGORIES = ("alcohol", "cigarettes", "cocaina", "meth", "positive", "sounds")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_api_key(media_root: str) -> str:
    """Load Pexels API key from env var or media/pexels.env."""
    key = os.environ.get("PEXELS_API_KEY")
    if key:
        return key.strip()
    env_file = Path(media_root) / "pexels.env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                return line.split("=", 1)[1].strip()
    sys.exit(
        "PEXELS_API_KEY not set and media/pexels.env not found.\n"
        "Get a free key at https://www.pexels.com/api/"
    )


def _get_json(url: str, api_key: str) -> tuple[dict, dict]:
    """Fetch JSON from the Pexels API. Returns (data, response_headers)."""
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Authorization": api_key,
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            headers = {k.lower(): v for k, v in resp.getheaders()}
            return json.loads(resp.read().decode("utf-8")), headers
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            sys.exit("Invalid Pexels API key (HTTP 401). Check your key.")
        if exc.code == 429:
            sys.exit("Rate limit exceeded (HTTP 429). Wait and retry.")
        raise


def _download(url: str, dest: Path, timeout: int = 60) -> bool:
    """Download a file. Returns True on success."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            dest.write_bytes(resp.read())
            return True
    except Exception as exc:
        print(f"  ! skip {url}: {exc}")
        return False


def _print_rate_limit(headers: dict) -> None:
    remaining = headers.get("x-ratelimit-remaining", "?")
    limit = headers.get("x-ratelimit-limit", "?")
    print(f"  (rate limit: {remaining}/{limit} remaining)")


def _pick_video_file(video_files: list[dict], prefer: str = "hd") -> dict | None:
    """Pick the best MP4 variant from the video_files array."""
    mp4s = [vf for vf in video_files if vf.get("file_type") == "video/mp4"]
    if not mp4s:
        return None
    mp4s.sort(key=lambda vf: vf.get("height", 0), reverse=True)
    thresholds = {"sd": 480, "hd": 720, "fhd": 1080, "uhd": 2160}
    max_h = thresholds.get(prefer, 720)
    for vf in mp4s:
        if vf.get("height", 0) <= max_h:
            return vf
    return mp4s[-1]  # smallest available if all exceed threshold


def _write_licenses(out_dir: Path, rows: list[list[str]]) -> None:
    """Append rows to _licenses.csv, creating header if needed."""
    if not rows:
        return
    lic = out_dir / "_licenses.csv"
    write_header = not lic.exists()
    with open(lic, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if write_header:
            w.writerow(["file", "license", "creator", "source_url"])
        w.writerows(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Fetch stock photos/videos from Pexels into media/<category>.",
    )
    ap.add_argument("--query", required=True, help="search terms")
    ap.add_argument("--category", required=True, choices=CATEGORIES)
    ap.add_argument("--count", type=int, default=8, help="number of results (max 80)")
    ap.add_argument("--media-root", default="media", help="path to the media/ folder")
    ap.add_argument(
        "--type", dest="media_type", default="photo", choices=("photo", "video"),
        help="media type to search",
    )
    ap.add_argument(
        "--size", default="large",
        choices=("original", "large2x", "large", "medium", "small"),
        help="photo size preset (ignored for video)",
    )
    ap.add_argument(
        "--orientation", choices=("landscape", "portrait", "square"),
        help="filter by orientation",
    )
    ap.add_argument(
        "--video-quality", default="hd", choices=("sd", "hd", "fhd", "uhd"),
        help="preferred video quality (ignored for photo)",
    )
    ap.add_argument(
        "--no-reencode", action="store_true",
        help="skip ffmpeg re-encode (default: re-encode to H.264+AAC if ffmpeg is available)",
    )
    args = ap.parse_args()

    api_key = _load_api_key(args.media_root)
    out_dir = Path(args.media_root) / args.category
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() else "-" for c in args.query.lower())[:24].strip("-")

    if args.media_type == "photo":
        _fetch_photos(api_key, args, out_dir, slug)
    else:
        _fetch_videos(api_key, args, out_dir, slug)


def _fetch_photos(api_key: str, args: argparse.Namespace, out_dir: Path, slug: str) -> None:
    params: dict[str, str | int] = {
        "query": args.query,
        "per_page": min(args.count, 80),
    }
    if args.orientation:
        params["orientation"] = args.orientation

    url = f"{PHOTO_API}?{urllib.parse.urlencode(params)}"
    print(f"Searching Pexels photos for: {args.query!r}")
    data, headers = _get_json(url, api_key)
    _print_rate_limit(headers)

    results = data.get("photos", [])[: args.count]
    if not results:
        print("No results.")
        return

    rows: list[list[str]] = []
    saved = 0
    for i, photo in enumerate(results, start=1):
        src_url = photo.get("src", {}).get(args.size)
        if not src_url:
            print(f"  ! no {args.size!r} URL for photo {photo.get('id')}")
            continue

        # Determine file extension from URL
        ext = ".jpg"
        url_path = urllib.parse.urlparse(src_url).path
        if "." in url_path:
            ext = "." + url_path.rsplit(".", 1)[-1].split("?")[0]
            if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                ext = ".jpg"

        dest = out_dir / f"px_{slug}_{i:02d}{ext}"
        if _download(src_url, dest):
            saved += 1
            photographer = photo.get("photographer", "")
            source = photo.get("url", "")
            rows.append([dest.name, "Pexels License", photographer, source])
            print(f"  [ok] {dest.name}  (by {photographer})")

    _write_licenses(out_dir, rows)
    print(f"\nDone. Saved {saved} photo(s) to {out_dir}. Licenses logged to _licenses.csv.")
    print("Review each image for clinical appropriateness before using with patients.")


def _fetch_videos(api_key: str, args: argparse.Namespace, out_dir: Path, slug: str) -> None:
    params: dict[str, str | int] = {
        "query": args.query,
        "per_page": min(args.count, 80),
    }
    if args.orientation:
        params["orientation"] = args.orientation

    url = f"{VIDEO_API}?{urllib.parse.urlencode(params)}"
    print(f"Searching Pexels videos for: {args.query!r}")
    data, headers = _get_json(url, api_key)
    _print_rate_limit(headers)

    results = data.get("videos", [])[: args.count]
    if not results:
        print("No results.")
        return

    rows: list[list[str]] = []
    saved = 0
    for i, video in enumerate(results, start=1):
        vf = _pick_video_file(video.get("video_files", []), args.video_quality)
        if not vf:
            print(f"  ! no MP4 variant for video {video.get('id')}")
            continue

        dl_url = vf["link"]
        res = f"{vf.get('width', '?')}x{vf.get('height', '?')}"
        dest = out_dir / f"px_{slug}_{i:02d}.mp4"

        reencode = not args.no_reencode and shutil.which("ffmpeg")
        ok = False
        if reencode:
            import tempfile, subprocess
            tmp = Path(tempfile.mktemp(suffix=".mp4"))
            if _download(dl_url, tmp, timeout=120):
                print(f"  Re-encoding to H.264 + AAC…")
                cmd = [
                    "ffmpeg", "-y", "-i", str(tmp),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-movflags", "+faststart",
                    str(dest),
                ]
                result = subprocess.run(cmd, capture_output=True, text=True,
                                       creationflags=subprocess.CREATE_NO_WINDOW
                                       if sys.platform == "win32" else 0)
                tmp.unlink(missing_ok=True)
                ok = result.returncode == 0
                if not ok:
                    print(f"  ! ffmpeg failed for {dest.name}")
            else:
                tmp.unlink(missing_ok=True)
        else:
            ok = _download(dl_url, dest, timeout=120)

        if ok:
            saved += 1
            user = video.get("user", {})
            creator = user.get("name", "")
            source = video.get("url", "")
            rows.append([dest.name, "Pexels License", creator, source])
            print(f"  [ok] {dest.name}  ({res}, by {creator})")

    _write_licenses(out_dir, rows)
    print(f"\nDone. Saved {saved} video(s) to {out_dir}. Licenses logged to _licenses.csv.")
    print("Review each clip for clinical appropriateness before using with patients.")


if __name__ == "__main__":
    main()
