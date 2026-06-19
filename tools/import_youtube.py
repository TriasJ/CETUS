"""OPTIONAL: import a (Creative-Commons) YouTube clip OFFLINE into the media library.

Downloads with yt-dlp and re-encodes to the safe playback profile (H.264 + AAC mp4)
with ffmpeg, so the patient-facing app plays a local file with no internet, no ads,
and no recommendations mid-session.

    pip install yt-dlp           # and install ffmpeg (system binary)
    python tools/import_youtube.py --url "https://youtu.be/..." --category alcohol --name bar_scene

IMPORTANT: Only import clips that are Creative-Commons licensed or that your clinic
has the right to use. You are responsible for the licensing of imported media.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CATEGORIES = ("alcohol", "cigarettes", "meth", "positive", "sounds")


def _require(binary: str) -> None:
    if shutil.which(binary) is None:
        sys.exit(f"'{binary}' not found on PATH. Install it first.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Import a CC YouTube clip into media/<category> as mp4.")
    ap.add_argument("--url", required=True)
    ap.add_argument("--category", required=True, choices=CATEGORIES)
    ap.add_argument("--name", required=True, help="output filename (without extension)")
    ap.add_argument("--media-root", default="media")
    ap.add_argument("--max-seconds", type=int, default=0, help="optional trim to first N seconds")
    args = ap.parse_args()

    _require("yt-dlp")
    _require("ffmpeg")

    out_dir = Path(args.media_root) / args.category
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / f"{args.name}.mp4"

    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.%(ext)s"
        print("Downloading…")
        subprocess.run(["yt-dlp", "-f", "bv*[ext=mp4]+ba[ext=m4a]/mp4",
                        "-o", str(raw), args.url], check=True)
        downloaded = next(Path(tmp).glob("raw.*"))
        print("Re-encoding to H.264 + AAC…")
        cmd = ["ffmpeg", "-y", "-i", str(downloaded)]
        if args.max_seconds > 0:
            cmd += ["-t", str(args.max_seconds)]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart",
                str(final)]
        subprocess.run(cmd, check=True)

    print(f"\nDone. Saved {final}. Confirm the clip is CC-licensed/cleared for clinical use.")


if __name__ == "__main__":
    main()
