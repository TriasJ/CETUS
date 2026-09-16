# CETUS Overhaul Plan — Session Modes, VAS Enhancement, Weighted Cues, Help Enrichment

## Context

CETUS currently has one implicit session mode (intense craving evocation) with a horizontal slider VAS and no neutral-cue concept. The user wants to:
1. Add two new session modes (Interspersed Neutral, Custom) alongside the existing Intense mode
2. Import weighted cue databases from research datasets (METH/OPI + Tobacco) in `docs/Módulo 5/`
3. Enhance the VAS craving scale (bigger, add circles and stars alternatives)
4. Enrich bilingual help files with new research and new feature documentation
5. Build a Custom mode combining all capabilities

User decisions:
- Neutral cues: copy 115 tobacco neutrals as starter + clinicians can add their own
- METH/OPI images: extract from PDFs using pymupdf, import weights from CSV
- VAS display: configurable before session, applied everywhere (baseline, periodic, endpoint)

Additional constraints (added during implementation):
- **No craving cues in last third**: In interspersed mode, craving cues must NOT appear in the final third of the playlist. Only neutral cues fill the last ~33%.
- **Dynamic neutral increase**: Optional setting — when craving is high, increase neutral cues dynamically until craving drops below a configurable threshold before showing the next craving cue.

---

## Phase 1: Data Layer (Schema, Models, Migrations)

### 1.1 Domain Models — `cravingcrave/domain/models.py`

Add `SessionMode` enum:
```python
class SessionMode(str, Enum):
    INTENSE = "intense"
    INTERSPERSED = "interspersed"
    CUSTOM = "custom"
```

Add fields to existing dataclasses:
- `CueConfig`: add `is_neutral: bool = False` and `craving_weight: float | None = None`
- `Session`: add `mode: str = SessionMode.INTENSE.value`

### 1.2 Schema Migration v6 — `cravingcrave/data/migrations.py`

Single migration adding three columns:
- `session.mode TEXT NOT NULL DEFAULT 'intense'`
- `cue_config.is_neutral INTEGER NOT NULL DEFAULT 0`
- `cue_config.craving_weight REAL`

Bump `CURRENT_VERSION` to 6. Update `schema.sql` for fresh installs.

### 1.3 Repositories — `cravingcrave/data/repositories.py`

- `SessionRepo.create()`: include `mode` in INSERT
- `SessionRepo._row()`: read `mode` with fallback `'intense'`
- `CueConfigRepo.create()`/`update()`/`_row()`: handle `is_neutral` and `craving_weight`

---

## Phase 2: Configuration — `cravingcrave/config.py`

Add new `AppConfig` fields:
```python
# Session mode
default_session_mode: str = "intense"

# Interspersed-mode parameters
interspersed_craving_pct: int = 5          # % of total cues that are craving
interspersed_craving_count: int = 0        # 0 = use pct; >0 = exact count
interspersed_min_exposure_sec: int = 5     # min seconds per cue before advance
interspersed_vas_on_neutral: bool = False  # prompt VAS on neutral cues?

# VAS display
vas_display_mode: str = "slider"           # "slider" | "circles" | "stars"
```

Update `ensure_dirs()` to create `media/neutral/` folder.

Load new settings in `cravingcrave/ui/context.py` → `_apply_settings()`.

---

## Phase 3: Media & Cue Import

### 3.1 Add "neutral" to built-in categories — `cravingcrave/services/media_library.py`

```python
BUILTIN_CATEGORIES = ("alcohol", "cigarettes", "meth", "positive", "sounds", "neutral")
```

### 3.2 Import script: Tobacco neutral images — `tools/import_tobacco_neutrals.py`

Standalone script that copies `docs/Módulo 5/Tabaco/Data/{110-224}.jpg` → `media/neutral/tobacco_neutral_{NNN}.jpg`. Handles filename quirks (spaces in some filenames like "112 .jpg").

### 3.3 Import script: METH/OPI images from PDFs — `tools/import_meth_opi.py`

Install `pymupdf` as dev dependency. Script that:
1. Opens each PDF (mmc1, mmc3, mmc4, mmc5) with `fitz`
2. Extracts embedded images from each page
3. Saves to `media/meth/`, `media/opioid/`, or `media/neutral/` based on CSV category mapping
4. Names files using the CSV's `ImageSetFile` column for traceability

### 3.4 Weight data reference — `cravingcrave/resources/cue_weights/`

Parse `docs/Módulo 5/METH AND OPI/...mmc2.csv` into JSON lookup files:
- `meth_opi_weights.json`: maps filename → {craving_mean, arousal_mean, valence_mean, category}
- Craving values normalized from 0-100 (CSV scale) to 0-10 (VAS scale): `weight = craving_mean / 10.0`

### 3.5 Weight lookup service — `cravingcrave/services/cue_weights.py`

```python
class CueWeightLookup:
    def lookup(self, filename: str, substance: str) -> float | None: ...
    def suggest_weight(self, media_path: str) -> float | None: ...
```

Loads bundled JSON references. Used when clinicians add cues to auto-populate `craving_weight`.

---

## Phase 4: Domain Logic — Playlist Building

### 4.1 Interspersed playlist — `cravingcrave/domain/playlist.py`

Keep existing `build_exposure_playlist()` unchanged. Add:

**`build_interspersed_playlist(craving_cues, neutral_cues, neutral_media, craving_pct, craving_count, rng)`**:
1. Determine craving count (from pct or explicit count)
2. Select craving cues sorted by appetitive_rank (graded escalation preserved)
3. Build neutral pool from patient-assigned neutrals + media library neutrals (wrapped as temporary CueConfig with `is_neutral=True`, `id=None`)
4. Randomly distribute craving cues among neutral stream
5. Return interleaved list

**`build_weighted_playlist(cues)`**: Like `build_exposure_playlist` but sorts by `craving_weight` when available, falling back to `appetitive_rank`.

**`build_playlist_for_mode(mode, craving_cues, ...)`**: Dispatcher that calls the right builder.

---

## Phase 5: Session Controller — `cravingcrave/session/session_controller.py`

### 5.1 Constructor changes
Add `mode: str = SessionMode.INTENSE.value` parameter. Store as `self.mode`.

### 5.2 New method: `should_prompt_vas()`
```python
def should_prompt_vas(self) -> bool:
    cue = self.current_cue()
    if cue and cue.is_neutral:
        return self.config.interspersed_vas_on_neutral
    return True
```

### 5.3 Habituation filtering
In `record_rating()`, only append to `self._values` if the cue is NOT neutral:
```python
if kind in (RatingKind.PERIODIC, RatingKind.PEAK, RatingKind.ENDPOINT):
    cue = self.current_cue()
    if cue is None or not cue.is_neutral:
        self._values.append(value)
```

### 5.4 Minimum exposure enforcement
Add `min_cue_seconds()` and `current_cue_dwell()` methods. The exposure screen calls these before allowing cue advance.

### 5.5 Write mode to session
In `begin()`, set `mode=self.mode` on the Session object.

---

## Phase 6: VAS Enhancement — New Widgets

### 6.1 Abstract base — NEW `cravingcrave/ui/widgets/vas_input.py`

```python
class AbstractVasInput(QWidget):
    valueChanged = Signal(int)
    def value(self) -> int: ...
    def set_value(self, v: int) -> None: ...
    def nudge(self, delta: int) -> None: ...
    def reset(self) -> None: ...
```

Plus factory function `create_vas_input(mode, vas_max, parent)`.

### 6.2 Refactor slider — `cravingcrave/ui/widgets/vas_slider.py`

- Rename `VasSlider` → `SliderVasInput`, inheriting `AbstractVasInput`
- Keep `VasSlider = SliderVasInput` alias for backward compat
- Make it BIGGER: increase min height to 64px, larger handle (40px), bigger groove (14px)
- Increase value label font size

### 6.3 Circles mode — NEW `cravingcrave/ui/widgets/vas_circles.py`

- 11 circles (0-10), progressively larger (diameter 24px→60px)
- Selected circle and below filled with PRIMARY color; rest outlined
- Custom `paintEvent` with `QPainter`
- Click or keyboard to select
- Same low/high labels and big numeric readout

### 6.4 Stars mode — NEW `cravingcrave/ui/widgets/vas_stars.py`

- 11 five-pointed stars (0-10), same size (~48px), drawn with `QPainter`
- Stars up to value filled gold/amber; rest outlined
- Click or keyboard to select

### 6.5 Update VasPrompt — `cravingcrave/ui/widgets/vas_slider.py`

Add `mode` parameter to `__init__`. Replace `self.slider = VasSlider(vas_max)` with `self.slider = create_vas_input(mode, vas_max)`.

### 6.6 Accessibility

All three modes implement `set_value()`/`nudge()`/`value()` — the existing `AccessibilityInput` keyboard path works automatically with no changes to `hotkeys.py`.

---

## Phase 7: UI — Session Setup & Exposure

### 7.1 Session Setup Screen — `cravingcrave/ui/screens/session_setup_screen.py`

Add **mode selector** (QComboBox) before substance selection:
- Intense / Interspersed / Custom
- When Interspersed or Custom: show interspersed params (craving %, craving count, min exposure time)
- Show neutral cue count from `media/neutral/`
- Pass `mode` through `window.start_exposure()`

### 7.2 Session Params Dialog — `cravingcrave/ui/widgets/session_params_dialog.py`

Add interspersed parameters (visible when mode is interspersed/custom):
- Craving percentage spinbox
- Craving count spinbox
- Min exposure time spinbox
- VAS on neutral cues checkbox

Update `overrides()` to include new fields.

### 7.3 Exposure Screen — `cravingcrave/ui/screens/exposure_screen.py`

**VAS skip logic**: In `_on_periodic()`, `_on_per_cue_timeout()`, `_maybe_prompt_after_n_cues()`:
```python
if not self.controller.should_prompt_vas():
    return  # neutral cue — skip VAS
```

**Minimum exposure enforcement**: In `_next_cue()`:
```python
min_sec = self.controller.min_cue_seconds()
if min_sec > 0 and self.controller.current_cue_dwell() < min_sec:
    return  # enforce minimum viewing time
```

**VAS display mode**: Pass `context.config.vas_display_mode` to VasPrompt.

**Neutral cue indicator**: Show "[neutral]" or a visual marker on the cue counter for neutral cues.

### 7.4 Summary Screen — `cravingcrave/ui/screens/summary_screen.py`

Show session mode in the summary metrics card.

### 7.5 Settings Screen — `cravingcrave/ui/screens/settings_screen.py`

Add VAS display mode combo in session options card. Add default session mode combo.

---

## Phase 8: Exports & Reports

### 8.1 Export — `cravingcrave/services/export.py`

Add `mode` to `SESSION_COLUMNS` in `export_sessions_summary()`.

### 8.2 Reports — `cravingcrave/domain/reports.py`

No structural changes needed. Neutral-cue ratings (if collected) are distinguishable via `cue_config_id` linkage to CueConfig rows with `is_neutral=True`.

---

## Phase 9: Help Files & i18n

### 9.1 New help sections — `resources/help/{en,es}.json`

Add 5 new sections:
| id | Title (en) | Insert after |
|----|-----------|-------------|
| `session_modes` | Session modes: Intense, Interspersed and Custom | `settings_help` |
| `interspersed_neutral` | Interspersed neutral stimuli | `session_modes` |
| `vas_display` | VAS display options: Slider, Circles, Stars | `vas` |
| `weighted_cues` | Weighted cue database | `adaptive_ordering` |
| `neutral_cues` | Neutral cues | `weighted_cues` |

Enrich existing sections:
- `cet`: cite new research (Sayette, Wang, Frontiers article, MOCIS dataset)
- `vas`: mention circles/stars display options
- `graded`: mention weighted database as ordering alternative
- `settings_help`: document new settings (mode, VAS display, min exposure)
- `references`: add new citations (Sayette et al. 2016, Wang et al. 2026, MOCIS article, Tobacco dataset)

### 9.2 New i18n keys — `resources/i18n/{en,es}.json`

~30 new keys covering:
- Mode selection: `setup.mode_label`, `setup.mode_intense`, `setup.mode_interspersed`, `setup.mode_custom`, descriptions
- VAS display: `vas.display_label`, `vas.display_slider`, `vas.display_circles`, `vas.display_stars`
- Interspersed params: `setup.interspersed_pct`, `setup.interspersed_count`, `setup.min_exposure_sec`
- Neutral cues: `substance.neutral`, `setup.neutral_count`, `setup.no_neutral`
- Weights: `cueconfig.weight_label`, `cueconfig.suggest_weights`
- Settings: `settings.vas_display_mode`, `settings.session_mode_title`

### 9.3 Regenerate docs

Run `scripts/gen_help_docs.py` to update `docs/manual/{en,es}.md`.

---

## Phase 10: QSS & Theme

- Enlarge VAS slider handle/groove in `resources/styles/app.qss`
- Add styles for CirclesVasInput, StarsVasInput
- Ensure all 5 themes (light, dark, high_contrast, impaired, classic) work with new widgets

---

## Implementation Order

| Step | What | Files | Depends on |
|------|------|-------|-----------|
| 1 | Data layer: models, migration v6, repos | models.py, migrations.py, repositories.py, schema.sql | — |
| 2 | Config: new fields, dir creation, setting load | config.py, context.py | Step 1 |
| 3 | Media library + neutral category | media_library.py, substances.py | Step 2 |
| 4 | Import tools: tobacco neutrals + METH/OPI | tools/import_tobacco_neutrals.py, tools/import_meth_opi.py | Step 3 |
| 5 | Weight data: JSON reference + lookup service | resources/cue_weights/*.json, services/cue_weights.py | Step 1 |
| 6 | Domain: playlist builders (interspersed, weighted) | domain/playlist.py | Steps 1, 3 |
| 7 | Session controller: mode, VAS skip, min exposure | session/session_controller.py | Steps 1, 2, 6 |
| 8 | VAS widgets: abstract base, circles, stars | widgets/vas_input.py, vas_circles.py, vas_stars.py, vas_slider.py | — |
| 9 | VAS integration: VasPrompt + exposure screen | vas_slider.py, exposure_screen.py | Step 8 |
| 10 | UI: session setup + params dialog + mode selector | session_setup_screen.py, session_params_dialog.py | Steps 6, 7 |
| 11 | UI: summary, settings, exports | summary_screen.py, settings_screen.py, export.py | Steps 7, 8 |
| 12 | i18n: all new keys (both locales) | i18n/en.json, i18n/es.json | Incremental |
| 13 | Help: new sections + enrichment (both locales) | help/en.json, help/es.json | Step 12 |
| 14 | QSS + themes | resources/styles/ | Steps 8, 9 |
| 15 | Tests | tests/ | All above |
| 16 | Regenerate help docs | scripts/gen_help_docs.py | Step 13 |

---

## Verification

1. **Tests**: Run `pytest tests/ -q` — all existing + new tests pass
2. **Lint**: Run `ruff check .` — no issues
3. **App launch**: Run `.venv\Scripts\python.exe -m cravingcrave` — verify:
   - Settings screen shows VAS display mode + session mode defaults
   - Session setup shows mode selector with Intense/Interspersed/Custom
   - Interspersed mode shows correct neutral/craving cue mix
   - VAS circles and stars render correctly, keyboard input works
   - Neutral cues skip VAS in interspersed mode
   - Minimum exposure time prevents early cue advance
   - Summary shows session mode
   - CSV export includes mode column
4. **Help**: F1 shows new sections, both languages
5. **Migration**: Delete data/cetus.db, relaunch — fresh schema includes new columns
6. **Import tools**: Run tobacco import, verify images in `media/neutral/`

---

## Critical Files Summary

### Modified
- `cravingcrave/domain/models.py` — SessionMode enum, CueConfig fields, Session mode
- `cravingcrave/domain/playlist.py` — interspersed + weighted builders
- `cravingcrave/data/migrations.py` — v6 migration
- `cravingcrave/data/schema.sql` — new columns for fresh installs
- `cravingcrave/data/repositories.py` — read/write new fields
- `cravingcrave/config.py` — new AppConfig fields, neutral dir
- `cravingcrave/session/session_controller.py` — mode, should_prompt_vas, min exposure
- `cravingcrave/ui/widgets/vas_slider.py` — SliderVasInput refactor, VasPrompt mode
- `cravingcrave/ui/widgets/session_params_dialog.py` — interspersed params
- `cravingcrave/ui/screens/session_setup_screen.py` — mode selector
- `cravingcrave/ui/screens/exposure_screen.py` — VAS skip, min exposure, display mode
- `cravingcrave/ui/screens/summary_screen.py` — show mode
- `cravingcrave/ui/screens/settings_screen.py` — VAS display + mode settings
- `cravingcrave/ui/context.py` — load new settings
- `cravingcrave/services/media_library.py` — add "neutral" category
- `cravingcrave/services/export.py` — mode in CSV
- `cravingcrave/resources/help/{en,es}.json` — 5 new sections + enrichments
- `cravingcrave/resources/i18n/{en,es}.json` — ~30 new keys
- `cravingcrave/resources/styles/app.qss` — bigger VAS, new widget styles

### New files
- `cravingcrave/ui/widgets/vas_input.py` — AbstractVasInput + factory
- `cravingcrave/ui/widgets/vas_circles.py` — CirclesVasInput
- `cravingcrave/ui/widgets/vas_stars.py` — StarsVasInput
- `cravingcrave/services/cue_weights.py` — weight lookup service
- `cravingcrave/resources/cue_weights/meth_opi_weights.json` — weight reference data
- `tools/import_tobacco_neutrals.py` — tobacco neutral image importer
- `tools/import_meth_opi.py` — METH/OPI PDF image extractor + weight importer
