# CETUS Clinical Feedback Plan — Bugs, UX, and New Features

## Context

Clinical peers tested the app after the session-modes overhaul and raised 11 points spanning bugs, UX polish, and feature requests. This plan addresses all of them in priority order.

---

## A. Bugs (must fix)

### A1. Video keeps playing during rating dialog (#3)
**Problem**: `CueView` has no `pause()`/`resume()`. When VAS overlay opens, video plays behind it.
**Fix**: Add `pause()` and `resume()` to `CueView`. In `exposure_screen._open_periodic_vas()`, `_mark_peak()`, and `_ask_baseline()`: call `self.cue_view.pause()`. In `_on_vas_submitted()`: call `self.cue_view.resume()`. Add config flag `pause_video_on_rating: bool = True` (toggleable, off shows old behavior).
**Files**: `cravingcrave/ui/widgets/cue_view.py`, `cravingcrave/ui/screens/exposure_screen.py`, `cravingcrave/config.py`

### A2. Video playback rules (#4)
**Problem**: Periodic timer fires every 30s regardless of video duration. Patient can't see the video.
**Rules** (per clinician):
- Videos **loop indefinitely by default** (existing behavior, now a toggleable config: `video_loop: bool = True`).
- Videos **must play fully at least once** before VAS can be prompted. The periodic timer defers if the video hasn't completed one full loop.
- Videos **are cut short at max exposure time**: when `min_cue_seconds` (or a new `max_cue_exposure_sec`) is reached, the video stops and VAS is prompted / cue advances regardless of playback position.
**Fix**: Connect `QMediaPlayer.mediaStatusChanged` in `CueView`. Track `_video_loops_completed: int` (reset on `show_video()`). Emit `videoLoopCompleted` signal on `EndOfMedia` transition. In `exposure_screen._on_periodic()`: if current cue is video and `_video_loops_completed < 1` → defer. Add `max_cue_exposure_sec: int = 0` config (0 = off; >0 = force advance/VAS after N seconds on any cue, cutting video short if needed).
**Files**: `cue_view.py`, `exposure_screen.py`, `config.py`

### A3. `_prev_cue()` bypasses minimum exposure time (#2 partial)
**Problem**: `_prev_cue()` has no `min_cue_seconds` guard. Patient can go backward without waiting.
**Fix**: Add the same guard to `_prev_cue()` as `_next_cue()` has.
**File**: `exposure_screen.py`

### A4. Dynamic neutral increase not wired (#6)
**Problem**: `should_skip_craving_cue()` exists in controller but is never called. Config fields `dynamic_neutral_enabled`/`dynamic_neutral_threshold` are not in the params dialog.
**Fix two parts**:
1. Add `dynamic_neutral_enabled` checkbox and `dynamic_neutral_threshold` spinbox to `SessionParamsDialog`. Include in `overrides()`.
2. Wire `should_skip_craving_cue()` into `exposure_screen._next_cue()`: when the next cue in the playlist is a craving cue and `should_skip_craving_cue()` returns True, skip it and show the next neutral instead.
**Files**: `session_params_dialog.py`, `exposure_screen.py`, `session_controller.py`

---

## B. UX Polish

### B1. GUI clutter / responsiveness (#1)
**Problem**: Settings screen, params dialog, and exposure screen clip at small sizes.
**Fixes**:
- **Params dialog**: Wrap the form in a `QScrollArea` so it scrolls on small screens. Add `setMinimumHeight(400)`.
- **Exposure screen**: Add `QScrollArea` to the right panel (`_right_box`) containing chart + intensity. Set `setWidgetResizable(True)`.
- **Session setup screen**: Wrap the interspersed params frame in a collapsible group or use the existing card's scroll.
**Files**: `session_params_dialog.py`, `exposure_screen.py`

### B2. Loop + min timing transparency (#2)
**Problem**: When autoscroll timer < min exposure time, hint flashes repeatedly. No visual feedback on timing.
**Fix**: Show a **discrete, toggleable** countdown indicator (default ON, config `show_min_exposure_hint: bool = True`). When min-exposure blocks advance, display a subtle small label near the cue counter: "⏱ 3s" counting down, fading out when time is met. NOT a modal or blocking message — just a small overlay text that doesn't interrupt the experience. When autoscroll is shorter than min exposure, auto-clamp autoscroll interval to >= min exposure (with a warning in the params dialog).
**Files**: `exposure_screen.py`, `session_params_dialog.py`, `config.py`

### B3. Separate Image Cue and Video Cue settings (#5)
**Fix**: Add a new "Cue Media" card in the Session page of Settings with two subsections:
- **Image cues**: (future: display duration, transition effects)
- **Video cues**: `pause_video_on_rating` toggle, `vas_wait_video_loop` toggle, default loop count
Group the existing `cue_audio_mode` combo here too (it's media-related, not session-level).
**File**: `settings_screen.py`

---

## C. New Features

### C1. Randomization audit and backlog support (#7, #8)
**Problem**: Peers want assurance cues are properly randomized and want a system to prevent repeated cues from losing effect through habituation.
**Fix**:
- Add a **cue usage tracker**: new `cue_exposure_count` column on `cue_config` (migration v7). Increment each time a cue appears in a session. The playlist builder can then deprioritize over-exposed cues.
- Add a **backlog rotation**: `build_interspersed_playlist()` and `build_exposure_playlist()` accept an optional `max_repeats` param. Cues shown > max_repeats times across sessions get lower priority, pushing fresher cues to the front.
- Show exposure counts in the cue config list: `[3] w=8.7 ×5 meth/mocis_mmc4_050.jpeg`
**Files**: `models.py`, `migrations.py`, `repositories.py`, `playlist.py`, `cue_config_screen.py`

### C2. Spaced repetition algorithm (#9) — DEFERRED
Deferred to a future iteration per clinician decision. Focus this round on bugs, wizard, and cue backlogging which addresses the habituation concern more directly.

### C3. Download tools: neutral/opioid categories (#10)
**Fix**: Update the fallback `CATEGORIES` list in both `tools/pexels_gui.py` and `tools/youtube_gui.py` to include `"neutral"` and `"opioid"`. Since the dynamic scan (`MEDIA_ROOT.iterdir()`) already discovers them when the folders exist, this only matters for the fallback case when `media/` doesn't exist yet.
**Files**: `tools/pexels_gui.py`, `tools/youtube_gui.py`

### C4. Patient Setup Wizard (#11) — HIGH PRIORITY
**Fix**: Create a new `PatientWizard` using `QWizard` with evidence-based guided pages:

**Page 1 — Patient Profile**
- Substance type, usage history (duration, frequency), current abstinence status
- These feed the evidence-based recommendations

**Page 2 — Session Mode Recommendation**
- Based on profile: if high reactivity/early treatment → recommend Interspersed Neutral
- If established in treatment → recommend Intense
- Explain each option with clinical rationale using **numbered citations** [1], [2], etc.
- Clinician can override the recommendation
- Citations from PubMed/scientific literature (searched before implementation) covering:
  CET effectiveness, interspersed neutral paradigms, VAS methodology, cue reactivity

**Page 3 — Cue Selection**
- Auto-suggest cues from the media library matching the substance
- Show available cue count, offer to add from library
- Recommend neutral cue ratio if interspersed mode chosen

**Page 4 — VAS & Timing Configuration**
- Recommend VAS display mode (suggest circles for touch-oriented patients)
- Recommend periodic VAS interval based on evidence
- For video cues: recommend pause-on-rating + wait-for-loop
- Min exposure time recommendation

**Page 5 — Safety & Coping**
- Configure crisis contacts
- Enable/disable auto-coping threshold
- Review safety plan

**Page 6 — Summary & Confirm**
- Show all chosen settings
- "Apply as defaults for this patient" button
- "Start first session" button

**Scientific citations**: Before implementing, search PubMed and relevant libraries (via MCP tools or WebSearch) for current evidence on:
- CET protocols (optimal session duration, cue count, graded vs random)
- Interspersed neutral stimuli paradigms (ratio, timing)
- VAS craving measurement best practices
- Video vs image cue effectiveness
- Habituation timelines and session spacing

Each wizard recommendation page shows numbered superscript citations [1], [2]… with full references accessible via a "References" button that opens the help system's references section. Citations stored in a JSON resource file (`resources/wizard_citations.json`) so they can be updated independently.

**Trigger logic**: 
- Auto-launches on first session for any patient with 0 prior sessions (`session_count == 0`)
- "Run Setup Wizard" button on the patient detail screen for re-running
- Settings saved per-patient via `app_setting` table (key: `wizard_complete:{patient_id}`)

**Files**: NEW `cravingcrave/ui/screens/patient_wizard.py`, `patient_screen.py`, `session_setup_screen.py`, `main_window.py`

---

## Implementation Order

| Step | What | Priority | Est. complexity |
|------|------|----------|----------------|
| 1 | A1: Video pause/resume during VAS | Bug | Medium |
| 2 | A2: Video-aware VAS timing | Bug | Medium |
| 3 | A3: Min exposure on `_prev_cue` | Bug | Trivial |
| 4 | A4: Wire dynamic neutral increase | Bug | Small |
| 5 | B1: Scrollable params dialog + right panel | UX | Small |
| 6 | B2: Min exposure countdown + autoscroll clamp | UX | Small |
| 7 | B3: Image/Video settings card | UX | Small |
| 8 | C3: Download tools categories | Feature | Trivial |
| 9 | C1: Cue exposure counter + backlog | Feature | Medium |
| 10 | C4: Patient Setup Wizard (QWizard) | Feature | Large |

C2 (spaced repetition) deferred to future iteration.

Steps 1-4 are bugs and should be done first. Steps 5-8 are quick polish. Steps 9-11 are features in order of complexity.

---

## Critical Files

### Modified
- `cravingcrave/ui/widgets/cue_view.py` — pause/resume, video loop signal
- `cravingcrave/ui/screens/exposure_screen.py` — video-aware VAS, min exposure guards, countdown
- `cravingcrave/ui/widgets/session_params_dialog.py` — dynamic neutral, scroll area
- `cravingcrave/ui/screens/settings_screen.py` — Image/Video settings card
- `cravingcrave/config.py` — new flags (pause_video_on_rating, vas_wait_video_loop)
- `cravingcrave/ui/context.py` — load new settings
- `cravingcrave/domain/playlist.py` — backlog rotation support
- `cravingcrave/data/migrations.py` — v7 (cue_exposure_count)
- `cravingcrave/domain/models.py` — CueConfig.exposure_count
- `cravingcrave/ui/screens/patient_screen.py` — wizard button, spaced rep display
- `tools/pexels_gui.py` — categories fallback
- `tools/youtube_gui.py` — categories fallback

### New files
- `cravingcrave/ui/screens/patient_wizard.py` — QWizard-based patient setup with evidence-based recommendations

---

## i18n — All Changes Bilingual

Every user-facing string, tooltip, wizard page text, help section, and citation must be implemented in BOTH `es.json` and `en.json` (Spanish primary, English secondary). This includes:
- Wizard page titles, descriptions, and recommendation text
- New config labels (pause_video_on_rating, video_loop, max_cue_exposure_sec, show_min_exposure_hint)
- Dynamic neutral increase labels in params dialog
- Cue exposure count display format
- Image/Video settings card labels
- Citation text in wizard_citations.json (bilingual: `{"en": "...", "es": "..."}` per citation)
- Updated help sections documenting all new features

---

## Verification

1. **Tests**: `pytest tests/ -q` — all existing pass + new tests for video pause, min-exposure guard
2. **Lint**: `ruff check cravingcrave/`
3. **i18n parity**: Verify `len(en.json keys) == len(es.json keys)`
4. **Manual testing**:
   - Open a session with video cues → VAS should NOT appear until video plays once → video should pause when VAS opens
   - Try advancing cue before min exposure → blocked, countdown shown
   - Open params dialog → dynamic neutral checkbox visible, scrollable on small screen
   - First-time patient → wizard auto-launches
   - Download tool → "neutral" and "opioid" categories appear in dropdown
4. **Build**: `pyinstaller cravingcrave.spec --noconfirm`
