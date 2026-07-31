# Changelog

All notable changes to CETUS. Dates are when the work was done in development.

## 0.7.1 — adaptive + random ordering guidance (2026-07)

### Added
- **Rule of thumb** in the *Adaptive cue ordering* Help topic (ES + EN) for combining adaptive
  and random order: applied suggested order with random **off** for graded low→high exposure;
  random **on** occasionally to strengthen/de-bias the learning (order shuffles, but every rating
  still feeds the model). Notes that random **overrides** the suggested order for that session.
- **Warning in the Parameters popup** under *Randomize cue order* (shown when adaptive ordering is
  enabled): random order overrides the suggested graded order for this session; learning is
  unaffected.

## 0.7.0 — adaptive cue ordering (2026-07)

### Added
- **Adaptive cue ordering** — CETUS learns, from the craving ratings it already records per cue,
  which signals provoke more craving for each patient, and offers a **suggested low→high order**
  in the cue library. A cue's reactivity = peak-on-cue − session baseline, averaged across
  sessions (baseline rows excluded), **shrunk toward a cross-patient population prior** (shared
  media file → substance × modality → global) so small samples don't dominate. The order is a
  **clinician-reviewed suggestion** (preview with score, n and a low-data flag → one-click Apply
  rewrites `appetitive_rank`); it never reorders a live session. Toggleable in Settings → Session.
- **Export the signal-order database** — per patient from the cue library, or all patients from
  Admin Center → Reports, plus a **population cue-reactivity baseline (CSV)**. Pseudonymous.
- A bilingual **"Adaptive cue ordering"** Help topic (with the honest confound caveat), and a
  generated **online manual** (`docs/manual/{en,es}.md`) mirroring the in-app Help.

## 0.6.1 — spin-box arrows fix (2026-07)

### Fixed
- **Spin-box up/down arrows were invisible** in every theme. Styling the `QSpinBox`
  `::up-button`/`::down-button` sub-controls (added in the 0.5.2 clipping fix) makes Qt drop its
  native arrows unless image assets are supplied. Removed that sub-control styling from the base
  and all theme QSS; the value-text clipping stays fixed via `min-height` while the platform draws
  visible arrows again.

## 0.6.0 — Admin Center + themes (2026-07)

A key-gated **Admin Center** (dashboard → *Admin*, reuses the admin key; no per-clinician roles)
plus selectable UI themes.

### Added
- **Backup & restore** — one-click backup of the whole dataset (SQLite DB via the online-backup
  API + media) to a zip with a manifest; restore writes a **pre-restore safety copy** first, then
  replaces the data and closes for a clean restart.
- **Patient data handling** — export a full per-patient bundle (zip of CSVs, pseudonymous code
  only), **anonymize** (clear name/birth-year/notes, keep sessions), and **hard delete** (DB
  cascade + removal of media unique to that patient). Destructive actions require typing the
  patient code, warn if no backup was made this session, and are audit-logged.
- **Clinician & clinic management** — rename, **disable/enable** (disabled accounts can't log in),
  delete (only when they own nothing), and **transfer patients** between clinicians (ownership
  moves; past sessions keep their original clinician). Clinic **name/address/email/phone** now
  appear in the PDF report header.
- **Cross-patient & per-clinician reporting** — a **cohort summary CSV**, **clinician activity
  CSV**, and a **cohort PDF** (totals, end-reason breakdown, per-patient table), with a
  per-clinician filter.
- **Storage** panel (data location, DB/media sizes, counts) and an **admin audit log**.
- **Themes** — Light (default), **Dark**, **High contrast**, **Low vision (large text)**, and
  **Classic Windows**, selectable in Settings → Appearance and applied live.
- New DB migrations: **v3** `admin_audit`, **v4** `clinician.disabled`. In-app Help
  (ES + EN) documents the Admin Center.

## 0.5.2 — readable inputs + contextual Help (2026-07)

### Added
- **Contextual Help buttons** — a *"How does it work?"* button on the **Settings** screen and
  the **Parameters** popup opens a new **"Settings: what each option does"** topic explaining
  how every setting/parameter changes the session (and Settings = defaults vs Parameters =
  per-session override).
- **Session flowchart** in Help (ES + EN) — a visual step-by-step diagram (setup → baseline →
  present cue → craving rises → interventions → periodic check → habituation → close) with a
  *"Patient:"* action on each step and the intervention keys.

### Fixed
- **Clipped input text** — spin boxes and dials in Settings and the Parameters popup no longer
  clip their values; inputs get a proper min-height and the spin/combo buttons get reserved
  space (regression from the 0.5.0 Options redesign).

## 0.5.1 — immersive fullscreen exposure (2026-07)

### Added
- **Immersive fullscreen** — in fullscreen the cue image/video fills the screen (full-bleed,
  on black) and the interface auto-hides: the chart and intensity sliders are hidden (intensity
  stays on the number keys `1/2/3` + `+/−`), and a **translucent bottom action bar** (counter +
  Peak / Cope / Positive / Next / End) **fades in on mouse-move or key-press and out after ~3s
  idle**. The red **ALTO** button stays visible at all times. Windowed mode is unchanged.

## 0.5.0 — UX polish: redesigned Options, number keys in fullscreen, adaptive prompts (2026-07)

### Added
- **Redesigned Options** — a master-detail layout: an **icon navigation list** (Session /
  User / Hotkeys / Substances) drives grouped **QGroupBox** pages with a persistent Save bar;
  keybindings use a compact two-column grid. Clinic-wide items (substances, logo, clinic name)
  are marked *"Shared with all users"*. Settings remain global/clinic-wide.
- **Number keys during exposure (all modes)** — the `1/2/3` axis + `+/−` scheme now works in
  normal exposure and **fullscreen**, not only keyboard-only mode. New keys **`4`** (open
  Afrontamiento) and **`5`** (open Positive Images). The controls also show their number as a
  reminder in windowed mode, and a **fading, non-interactive hint** lists the keys on entering
  fullscreen.
- **Adaptive craving prompts** — optional *"measure craving after each afrontamiento"* and
  *"measure craving every N cues"*, in addition to the fixed periodic timer. Both off by
  default (Settings → Session → Advanced).
- **Pre-session Parameters popup** — a *Parameters…* button on the setup screen opens a dialog
  for per-session run options: **random order, loop, auto-advance, keyboard-only, time limit,
  start in fullscreen**. Every option also has a **default in Ajustes** (Session → run options);
  the popup seeds from those defaults, remembers the **last config used per patient**, and
  applies to that run only (clinic-wide defaults untouched).
- **Recursive folder import** — *Add folder…* in cue configuration now imports every media
  file in the chosen folder **and its subfolders**.
- In-app **Help** (ES + EN): a new **"Session workflow"** topic walks through a session end to
  end (baseline → graded cues → down-regulation + coping → periodic craving → habituation →
  close) and the shortcuts topic documents keys 4/5 and numbers-in-fullscreen.

## 0.4.0 — auto-scroll, coping export, keyboard accessibility, installers (2026-07)

### Added
- **Auto-scroll cues** — optional hands-free advance of the shown cue, after each craving
  rating and/or every N seconds; both off by default and configurable in Settings.
- **Qualitative coping export** — the four USCS ("afrontamiento") free-text responses now
  export to a dedicated **CSV** (one row per response: code, session, substance, time, skill,
  text) and appear in the **PDF reports**; the timeline CSV gained an ISO timestamp column.
  Uses only the pseudonymous patient code. Blank responses are preserved (used-but-empty vs
  skipped is now distinguishable).
- **Keyboard accessibility** — a toggleable **keyboard-only mode** for the exposure session,
  built for an adaptive keyboard (Enter, +, −, arrows, 0–9): arrows switch cues; `1/2/3`
  select the size/blur/dim axis and `+/−` adjust it; `0` mutes; the craving rating is typed
  as a digit and confirmed with Enter. On-screen legend, active-axis highlight, works in
  full screen, and STOP (Esc) always available. A central **hotkey registry** drives all
  shortcuts and a **Settings → Keyboard shortcuts** page lets you remap any action (STOP
  locked for safety; accessible-mode keys restricted to the adaptive set).
- **Multi-OS installers** — Windows (Inno Setup), macOS (`.dmg` from an `.app` bundle) and
  Linux (AppImage), built per-OS by a `Release` GitHub Actions workflow on a `v*` tag.
  Placeholder app icon (PNG/ICO/ICNS). See `packaging/README.md`.
- In-app **Help** updated (ES + EN) to document all of the above.

### Changed
- **Data location** — external `data/` and `media/` now resolve per build: portable builds
  keep them next to the executable (`portable.txt` marker or an existing `data/` folder, so
  every current deployment is preserved), while installed builds use the standard per-OS user
  directory (`%APPDATA%\CETUS`, `~/Library/Application Support/CETUS`, `~/.local/share/CETUS`).
- Version → 0.4.0.

## 0.3.0 — localization (2026-07)

Bilingual UI with a drop-in mechanism for adding more languages.

### Added
- **Localization / i18n** — the UI is now bilingual: **Spanish (default)** and **English**.
  Every string resolves through `tr()` against `resources/i18n/<code>.json`; the in-app manual
  is translated per locale (`resources/help/<code>.json`, 18 topics) with citations preserved.
- **Live language switcher** — a selector on the **login screen** and in **Settings → Idioma /
  Language**. Changing language re-renders the current screen immediately (no restart) and
  persists the choice (`app_setting` key `locale`) for the next launch.
- **Auto-discovery** — `available_locales()` scans the locale files and reads each one's native
  name (`_language.name`), so a new language appears in both switchers with **no code changes**.
  New `docs/LOCALIZATION.md` documents how to add a language.
- Graceful fallbacks: a missing UI key returns the key; a missing translated manual falls back
  to the default-locale Help (never an empty window).
- Tests: locale key-parity across all languages, help-topic parity, auto-discovery, and the
  live switcher (Settings + login).

### Changed
- Startup applies the DB-persisted locale after the context loads, so the clinic's saved choice
  wins over the bootstrap default. Version → 0.3.0.

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
