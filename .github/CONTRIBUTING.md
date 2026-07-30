# Contributing to CETUS

Thanks for your interest. CETUS is a clinician-supervised, non-VR Cue Exposure Therapy
(CET-USCS) desktop app. It is an **adjunct** to therapy and **not a medical device** —
please keep that framing in mind for any user-facing or documentation change.

## Ground rules

- **Never commit clinical data or secrets.** The `data/` folder (SQLite DB with
  patient/clinician records) and any API keys are git-ignored — keep it that way. Do not
  add real patient media to the repo; only Creative-Commons / owned samples.
- **Keep the safety features intact.** The always-on ALTO panic button, consent gating,
  and crisis contacts are non-negotiable. Don't add a path that can start an exposure
  without consent or hide the panic button.
- **Be honest about evidence.** CET's efficacy is small/mixed/debated — don't add copy that
  overstates it. See `docs/MECHANISMS.md`.

## Dev setup

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\activate   |  macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
python run.py
```

## Before opening a PR

```bash
QT_QPA_PLATFORM=offscreen pytest -q     # all tests must pass
python scripts/functional_test.py       # end-to-end smoke (9/9)
ruff check .                            # lint (advisory for now)
```

- Add or update tests for any behavior change. The domain/data layers (`cravingcrave/domain`,
  `cravingcrave/services`) are Qt-free and should stay unit-testable without a GUI.
- Keep the Spanish UI strings in `cravingcrave/resources/i18n/es.json` (mirror new keys in
  `en.json`); document new features + their scientific basis in the in-app Help
  (`resources/help/es.json`) and `docs/`.
- Match the surrounding code style: `from __future__ import annotations`, type hints,
  small focused functions. Line length 100 (`ruff`).

## Architecture in one line

`ui/` (PySide6) → `session/` (orchestration) → `domain/` (pure rules) → `data/` (sqlite) →
`services/`. `domain/` and `session/` import no Qt.

## Reporting security / privacy issues

See [`SECURITY.md`](SECURITY.md) — please report privately, not in a public issue.
