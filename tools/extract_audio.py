"""Extract audio tracks from video files into standalone .m4a cue files.

Useful for creating audio-only cues from video cues that have provocative
audio content (e.g., bar ambience, glass clinking, pouring sounds).

    python tools/extract_audio.py media/alcohol/px_beer_01.mp4
    python tools/extract_audio.py media/alcohol/*.mp4 --output media/sounds/

If --output is omitted, audio files are placed next to the source video.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract audio from video files into .m4a cues.")
    ap.add_argument("files", nargs="+", help="video files to extract audio from")
    ap.add_argument("--output", "-o", default=None, help="output directory (default: same as source)")
    ap.add_argument("--prefix", default="audio_", help="filename prefix (default: audio_)")
    args = ap.parse_args()

    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg not found on PATH. Install it first.")

    out_dir = Path(args.output) if args.output else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    for fpath in args.files:
        src = Path(fpath)
        if not src.exists():
            print(f"  ! not found: {src}")
            continue
        dest_dir = out_dir or src.parent
        dest = dest_dir / f"{args.prefix}{src.stem}.m4a"
        print(f"Extracting {src.name} → {dest.name}...", end="")
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-vn", "-c:a", "aac", "-b:a", "128k", str(dest)],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode == 0:
            print(f" ✅ ({dest.stat().st_size // 1024} KB)")
        else:
            print(f" ❌ (no audio track or ffmpeg error)")
            dest.unlink(missing_ok=True)

    print("\nDone. Place .m4a files in the appropriate media/<category>/ folder to use as cues.")


if __name__ == "__main__":
    main()
