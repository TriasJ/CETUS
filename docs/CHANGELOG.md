# Changelog

All notable changes to CETUS. Dates are when the work was done in development.

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
