# Changelog

All notable changes to CETUS. Dates are when the work was done in development.

## 0.2.0 — hardening, fullscreen, references (2026-06)

Optimization, professionalization, and documentation pass.

### Added
- **Fullscreen / kiosk mode** — `F11` toggles fullscreen app-wide (panic overlay re-anchors
  automatically); documented in Help and on the login screen.
- **Behavioral-mechanisms documentation** — new `docs/MECHANISMS.md`, a README "Scientific
  basis & behavioral mechanisms" section, and an in-app Help topic ("Mecanismos"), each citing
  the evidence (Carter & Tiffany 1999, Kiyak 2022, Powell 1993, Price 2010, Heckman 2013,
  Schröder 2024, Lütt 2026, Mellentin 2017/2019, Ekhtiari 2022) with honest efficacy framing.
- **Application logging** — rotating `data/cetus.log` + console via `cravingcrave/logging_setup.py`.
- **CI** (`.github/workflows/ci.yml`: ubuntu+windows × py3.11/3.12, offscreen pytest, ruff),
  **ruff** config, and community-health files (CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, .editorconfig).

### Fixed / hardened
- Export writes (CSV/PNG/PDF, session + full-patient) are now guarded — failures show an error
  dialog instead of a false "saved", and are logged.
- Patient-create / clinician-create errors are narrowed to `sqlite3.IntegrityError` for the
  "duplicate" message; other DB/disk errors are surfaced honestly and logged (no longer
  mislabeled as a duplicate code).
- Defense-in-depth guard against starting an exposure with an empty cue playlist.

### Changed
- Finished the CravingCrave→CETUS brand cleanup: CSV export prefix `cetus_…`; default admin
  key `cetus-admin` (internal package id `cravingcrave` intentionally kept). Version → 0.2.0.
- Dev dependencies pinned for reproducibility; added a `cetus` console-script alias.

## 0.1.0 — initial release prep (2026-06)

First public-ready version. Core CET-USCS therapeutic loop plus clinic features.

### Core therapeutic loop
- Consent-gated session: graded cue exposure (image/video/audio) on a `QGraphicsView`
  surface with patient-controlled **shrink / blur / dim / mute**.
- Craving **VAS (0–10)** at baseline/peak/endpoint + periodic; live habituation curve;
  configurable habituation criterion (threshold + consecutive low ratings).
- Guided **USCS** coping (4 steps), **positive counter-stimuli gallery**, ambient sound bed.
- Always-on **ALTO** panic button (Esc) → calm screen with crisis contacts.

### Clinic / data
- Multi-patient dashboard, local clinician login (PBKDF2), pseudonymous patient codes.
- Per-patient cue configuration; batch + whole-folder media import; enable/disable all.
- Patient edit/archive (archive hides without deleting data).
- **Custom substances** beyond the built-in 3 (Ajustes), data-preserving.
- Admin recovery (Ctrl+Shift+A) + offline `tools/admin_reset.py`; in-app "Agregar clínico".
- SQLite with migrations (schema v2: clinician notes per session).

### Reports
- Per-session detail (annotated curve, evidence-based metrics, per-cue reactivity with the
  highest-reactivity cue highlighted, coping responses, clinician notes) — two-column layout.
- Cross-session progress: baseline/peak/endpoint + mean-exposure trends, habituation slope,
  spontaneous recovery, coping mix, end-reason mix.
- Export: **CSV** (PII-safe) and **A4-landscape PDF** with print-themed charts (never
  cropped), optional **clinic logo + name** header, and a **toggle for clinician notes**.
- Metrics grounded in PubMed (Schröder 2024, Lütt 2026, Powell 1993, Price 2010), framed
  as descriptive/exploratory.

### Quality of life
- Exposure keyboard shortcuts (T/D/O/M/R, ← →, L loop, Esc); randomized cue order.
- Spanish UI throughout (`resources/i18n/es.json`); CHM-style in-app Help (F1).
- Enlarged, legible Settings; scroll areas where content grows.

### Packaging / distribution
- One-file PyInstaller build (`cravingcrave.spec`); Windows media-backend fix for the
  QtMultimedia ffmpeg plugin.
- Cross-platform build scripts (`build.ps1`, `build.sh`); MIT license; curated CC sample
  media so a fresh clone runs out-of-the-box.

### Tests
- ~70 pytest (domain/data/services + offscreen GUI) and an end-to-end functional harness.
