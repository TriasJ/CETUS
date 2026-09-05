# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is CETUS

CETUS is a clinician-supervised, non-VR Cue Exposure Therapy (CET-USCS) desktop app for addiction treatment. Python 3.13 + PySide6, SQLite, bilingual UI (Spanish default, English). The on-disk folder is `CravingCrave`, the Python package is `cravingcrave`, and the product brand is **CETUS**. Published privately at `github.com/TriasJ/CETUS`.

## Commands

```bash
# Run the app
.venv\Scripts\python.exe -m cravingcrave

# Run all tests (pytest, ~170 tests, <10 seconds)
.venv\Scripts\python.exe -m pytest tests/ -q

# Run a single test file
.venv\Scripts\python.exe -m pytest tests/domain/test_habituation.py -v

# Run a single test by name
.venv\Scripts\python.exe -m pytest tests/ui/test_session_flow.py -k "test_baseline" -v

# Lint
.venv\Scripts\python.exe -m ruff check .

# Format
.venv\Scripts\python.exe -m ruff format .

# Regenerate help manual from in-app JSON
.venv\Scripts\python.exe scripts/gen_help_docs.py

# Generate screenshots for docs
.venv\Scripts\python.exe scripts/make_screenshots.py

# Build frozen exe (PyInstaller)
.venv\Scripts\pyinstaller cetus.spec
```

## Architecture

### Layer cake

```
ui/screens/          ← PySide6 screens (login, dashboard, setup, exposure, summary, settings, calm)
ui/widgets/          ← Reusable widgets (VAS slider, cue view, intensity controls, USCS coping panel)
session/             ← Session controller (QObject) + state machine (CONSENT→BASELINE→EXPOSURE→ENDPOINT→SUMMARY)
services/            ← Business logic (auth, media library, crisis contacts, i18n, help, export)
domain/              ← Pure functions (habituation rule, VAS clamping, playlist building, reports)
data/                ← SQLite (schema.sql, migrations, repositories)
config.py            ← AppConfig dataclass (all defaults, overridable via app_setting table)
```

### Session flow

The exposure session is the core clinical feature:
1. **SessionSetupScreen** — clinician picks substance, reviews cue count, optional ambient sound, consent
2. **ExposureScreen** — patient views cues; periodic VAS timer prompts craving (default 30s); intensity controls (shrink/blur/dim/mute); coping panel; positive gallery; panic button
3. **SessionController** (QObject) — orchestrates state, records ratings/coping/intensity to DB, checks habituation
4. **Summary** — session report with habituation slope

### Configuration pattern

`AppConfig` fields → loaded from `app_setting` key-value table via `_apply_settings()` in `ui/context.py` → saved in `settings_screen.py._save()` by writing both the in-memory config and the DB row. Per-session overrides use `dataclasses.replace()` via `SessionParamsDialog.overrides()`.

### i18n

Flat JSON files at `resources/i18n/{en,es}.json`. All user-facing text goes through `tr("dotted.key")` with optional `tr("key", name=value)` interpolation. Spanish-first; English is the secondary locale.

### Help system

`resources/help/{en,es}.json` — array of `{id, title, html}` sections. Loaded by `services/help.py`, rendered in `HelpDialog` (CHM-like: TOC left, content right). `scripts/gen_help_docs.py` regenerates `docs/manual/{en,es}.md` from these.

### Media library

Cue media lives in `media/<category>/` (alcohol, cigarettes, cocaina, meth, positive, sounds). `.gitignore` excludes `/media/*/*` except `.gitkeep`, `sample_*`, `_SAMPLES.csv`. Each category has a `_licenses.csv` sidecar. File naming: `{source_prefix}_{slug}_{NN}.{ext}` — prefixes: `oa_` (Openverse), `fs_` (Freesound), `wm_` (Wikimedia), `gen_` (Gemini), `px_` (Pexels). `g{NN}_` intensity-grading prefix is added post-download.

### Offline content tools

Standalone scripts in `tools/` — each self-contained (no cross-tool imports). CLI fetchers are stdlib-only; GUI tools use PySide6.

### Intensity / down-regulation

`CueView.set_intensity(scale_pct, blur_pct, dim_pct, muted)` — four levers. `IntensityControls` widget has `_size`, `_blur`, `_dim` QSliders + mute toggle. `state()` returns `(scale, blur, dim, muted)`. `reset()` snaps to 100/0/0/False (respects slider min/max ranges).

## Conventions

- **Imports**: explicit, granular PySide6 imports (`from PySide6.QtWidgets import QLabel, QPushButton`), never wildcards
- **Ruff**: line-length 100, target py311; `E702` (compact `a; b`) is allowed in UI layout code
- **Tests**: `pytest` + `pytest-qt`; test files mirror the source tree (`tests/domain/`, `tests/ui/`, etc.); UI tests use `conftest.py` in `tests/ui/` with `qtbot` fixtures
- **Settings persistence**: always write to both the in-memory `AppConfig` field AND the `app_setting` row via `s.set(key, str_value)`, using `"1"/"0"` for bools
- **Version**: single source of truth in `cravingcrave/__init__.py.__version__`; also in `pyproject.toml`
- **Clinical data**: `/data/` is gitignored (patient PII); never committed
- **Secrets**: `.env`, `*.key`, `*.pem`, `/media/*.env` are gitignored
- **Theme**: palette constants in `ui/theme.py` (PRIMARY=#2a9d8f, DANGER=#e63946, etc.); QSS stylesheets in `resources/styles/`
- **Windows-first**: the app targets Windows desktops; `sys.platform == "win32"` guards appear in media/build code; video playback requires H.264+AAC MP4 (Windows Media Foundation backend)
