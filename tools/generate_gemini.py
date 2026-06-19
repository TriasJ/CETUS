"""OPTIONAL: generate cue / counter-stimuli images with the Google Gemini API.

Uses the `google-genai` SDK and the `gemini-2.5-flash-image` model ("nano-banana").
Requires an API key in the GEMINI_API_KEY environment variable.

    pip install google-genai
    set GEMINI_API_KEY=...        (Windows)   /   export GEMINI_API_KEY=...  (bash)
    python tools/generate_gemini.py --prompt "calm forest path, soft light" --category positive --count 3

Use sparingly and review every image. Prefer real CC media (fetch_open_access.py)
for substance cues so exposure is ecologically valid; generation is most useful for
neutral/positive counter-stimuli.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

MODEL = "gemini-2.5-flash-image"
CATEGORIES = ("alcohol", "cigarettes", "meth", "positive", "sounds")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate images via Gemini into media/<category>.")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--category", required=True, choices=CATEGORIES)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--media-root", default="media")
    args = ap.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY is not set. Export it before running.")

    try:
        from google import genai
    except ImportError:
        sys.exit("google-genai not installed. Run: pip install google-genai")

    out_dir = Path(args.media_root) / args.category
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() else "-" for c in args.prompt.lower())[:24].strip("-")
    client = genai.Client(api_key=api_key)

    saved = 0
    for i in range(1, args.count + 1):
        resp = client.models.generate_content(model=MODEL, contents=[args.prompt])
        for part in resp.candidates[0].content.parts:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                dest = out_dir / f"gen_{slug}_{i:02d}.png"
                dest.write_bytes(inline.data)
                saved += 1
                print(f"  [ok] {dest.name}")
    print(f"\nDone. Generated {saved} image(s) in {out_dir}. Review before clinical use.")


if __name__ == "__main__":
    main()
