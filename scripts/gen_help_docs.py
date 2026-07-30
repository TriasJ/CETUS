"""Generate the GitHub manual pages from the in-app Help JSON.

Reads ``cravingcrave/resources/help/{es,en}.json`` and writes ``docs/manual/{es,en}.md`` so the
website docs stay in sync with the F1 Help inside CETUS. The section HTML is emitted mostly as-is
(GitHub renders headings, lists, tables, bold/italic; inline colours are dropped by its sanitizer).

Run from the repo root:  python scripts/gen_help_docs.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cravingcrave import __version__  # noqa: E402

HELP_DIR = ROOT / "cravingcrave" / "resources" / "help"
OUT_DIR = ROOT / "docs" / "manual"
_LEAD_H2 = re.compile(r"^\s*<h2>.*?</h2>", re.IGNORECASE | re.DOTALL)


def _slug(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s+", "-", s)


def _render(locale: str) -> str:
    data = json.loads((HELP_DIR / f"{locale}.json").read_text(encoding="utf-8"))
    sections = data["sections"]
    intro = ("_Auto-generated from CETUS's in-app Help (press **F1** in the app). "
             f"Do not edit by hand — run `scripts/gen_help_docs.py`. CETUS v{__version__}._")
    lines = [f"# {data['title']}", "", intro, "", "## Contents", ""]
    lines += [f"- [{s['title']}](#{_slug(s['title'])})" for s in sections]
    lines.append("")
    for s in sections:
        body = _LEAD_H2.sub("", s["html"]).strip()   # drop duplicate <h2>; use a markdown heading
        lines += ["---", "", f"## {s['title']}", "", body, ""]
    return "\n".join(lines) + "\n"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for locale in ("en", "es"):
        out = OUT_DIR / f"{locale}.md"
        out.write_text(_render(locale), encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
