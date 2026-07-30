# CETUS — Admin Center (design spec)

## Context & goal
CETUS today has no real admin surface: any logged-in clinician can reach everything, and the
only gate is a single global **admin key** on the login `Ctrl+Shift+A` recovery dialog (which can
only create clinicians, reset passwords, and change the key). Clinics asked for admin
quality-of-life: safe **patient-data handling**, **cross-patient / per-clinician reporting**,
**clinician & clinic management**, and **app themes**.

This spec defines an **Admin Center**: one key-gated area that hosts these tools, built in phases
so the highest-risk pieces are protected by a backup first.

**Confirmed decisions**
- **Permissions:** keep the **single global admin key** (no per-clinician roles). Every admin
  tool lives behind that gate. The default `cetus-admin` keeps its red "change me" warning.
- **Transfer patients** = reassign patient *ownership* (`patient.created_by`); each past
  `session.clinician_id` is left untouched as the historical record.
- **Clinicians are disabled, not deleted**, when they own data; hard-delete is allowed only when a
  clinician owns no patients and ran no sessions.
- **Build order (data-safety first):** backup/restore ships before any destructive tool.

## Non-goals
- No cloud sync, no networked multi-site, no encryption-at-rest changes.
- No per-clinician *preferences* (settings stay clinic-global).
- No RBAC/role system.

---

## Cross-cutting architecture (shared by all phases)

**Admin gate (reused).** `AuthService.verify_admin_key` already gates the login dialog. Extract a
tiny reusable prompt: `require_admin(parent, context) -> bool` (a small modal: password field →
`verify_admin_key`). Used by the dashboard "Admin" entry and anywhere else that opens the Admin
Center. The default-key red warning (`admin_key_is_default`) shows on the gate and in the Center.

**Admin Center screen.** New `AdminCenterScreen(QWidget)` swapped into the MainWindow stack (like
`SettingsScreen`), reachable via a dashboard **"Admin"** button (key-gated) and an **"Open Admin
Center"** button added to the existing `AdminDialog` after key verification. It reuses the
Settings master-detail visual (`QListWidget` icon nav + `QStackedWidget`, the `_draw_nav_icon`
pattern, `QGroupBox` cards). Nav pages are added per phase:
- Phase 0.6.0: **Backup**, **Storage**, **Audit log**
- 0.6.1: **Data** (per-patient handling)
- 0.6.2: **Clinicians**, **Clinic**
- 0.6.3: **Reports** (cohort / per-clinician)

**Audit log (shared).** New table `admin_audit(id, ts, actor, action, detail)` (migration v3) and
`services/audit.py::AuditRepo.log(action, detail, actor)` + `list_recent(limit)`. `actor` =
current clinician username (or `"admin"` if none). Every sensitive admin action logs one row.
Viewer = read-only newest-first list on the Audit page.

**i18n / help / tests / theme** conventions follow the existing project rules (strict es/en key
parity; help topic parity; offscreen pytest; ruff clean). New Admin strings use an `admin.*`
i18n prefix. A new help topic `admin_center` (both locales, same index) documents the Center and
is linked from a Help button on the Admin screen.

---

## Phase 0.6.0 — Admin Center foundation + Backup/Restore  *(implement first)*

### Backup & restore service — `cravingcrave/services/backup.py`
- `create_backup(config, dest_zip: Path) -> dict`:
  1. Snapshot the SQLite DB with the **`sqlite3` online backup API** into a temp file (consistent,
     no-lock copy) — never zip the live file directly.
  2. Write a `manifest.json` (app_version, created_at, schema_version, counts:
     patients/sessions/clinicians, media_file_count).
  3. Zip: `cravingcrave.db` (the snapshot) + `media/**` tree + `manifest.json`.
  Returns the manifest dict. Pure of Qt so it is unit-testable.
- `read_manifest(zip_path) -> dict` and `restore_backup(config, zip_path) -> dict`:
  - Validate it is a CETUS backup (manifest present) and schema_version ≤ current.
  - Copy the *current* DB+media to a `pre-restore-<stamp>` safety zip first.
  - Close the DB connection, extract DB + media into `data_dir`/`media_root`, and signal the UI
    that a **restart is required** (restore does not hot-swap the live connection).
- Media path uses `paths.media_root()`; DB uses `paths.db_path()`.

### UI (Admin Center → Backup page)
- **Create backup** button → `QFileDialog` save (default `cetus_backup_<stamp>.zip` under
  `data_dir`) → `create_backup` → success box with counts → `audit.log("backup_create", ...)`.
- **Restore backup** button → open zip → show manifest summary (date, counts) → **confirm** →
  `restore_backup` → `audit.log("backup_restore", ...)` → modal "Restart CETUS to finish" (the app
  keeps running on the old DB until restart).

### Storage page (read-only)
Data location (`paths.db_path()` dir), DB file size, media folder size (walk), and
patient/session/clinician counts (repo `count()` / `len(list_*)`). A **"Open data folder"** button
(`QDesktopServices.openUrl`).

### Audit page
Read-only newest-first list from `audit.list_recent(200)` (ts · actor · action · detail).

### Data / schema
- Migration **v3**: `CREATE TABLE admin_audit (id INTEGER PRIMARY KEY, ts TEXT NOT NULL,
  actor TEXT, action TEXT NOT NULL, detail TEXT)`. Bump `CURRENT_VERSION = 3`.

### Critical files (0.6.0)
- NEW `cravingcrave/services/backup.py`, `cravingcrave/services/audit.py` (+ `AuditRepo` wiring in
  `repositories.py`/context), `cravingcrave/ui/screens/admin_center_screen.py`,
  `cravingcrave/ui/widgets/admin_gate.py` (the `require_admin` prompt).
- EDIT `data/migrations.py` (v3 + table), `ui/main_window.py` (`show_admin_center`),
  `ui/screens/dashboard_screen.py` (key-gated Admin button), `ui/screens/admin_dialog.py`
  (Open-Admin-Center button), i18n `es/en` (`admin.*`), help `es/en` (`admin_center` topic).

### Tests (0.6.0)
- `backup.create_backup` produces a zip containing `cravingcrave.db` + `manifest.json` + media
  entries; manifest counts match the DB.
- Round-trip: create backup → mutate DB (add a patient) → `restore_backup` into a fresh data dir →
  reopened DB matches the backup (patient absent). Uses tmp dirs + a temp `AppContext`.
- `restore_backup` writes a pre-restore safety zip and rejects a non-CETUS zip.
- `AuditRepo.log`/`list_recent` round-trip; migration v3 applies idempotently.
- `require_admin` returns False on wrong key, True on right key (monkeypatch the prompt).
- i18n + help parity (automatic) and a smoke test that `AdminCenterScreen` builds with 3 pages.

### Verification (0.6.0)
`pytest -q` green, `ruff` clean; render the Admin Center pages offscreen; manually create a backup
zip, inspect it, and restore into a scratch data dir. Bump to **0.6.0**, CHANGELOG, ship.

---

## Later phases (design-level; each gets its own plan + release)

**0.6.1 — Patient data handling (destructive; backup exists first).** Admin Center **Data** page
with a patient picker: **Export full bundle** (zip of this patient's existing CSVs —
sessions-summary + per-session timelines + coping — via `export.py`, composed, no new PII columns);
**Anonymize** (`PatientRepo.anonymize(id)` clears `display_name`/`birth_year`/`notes`, keeps `code`
+ sessions); **Hard delete** (`PatientRepo.delete(id)` relying on schema `ON DELETE CASCADE`, plus
remove that patient's media files that no other patient references — cue media is per-patient, so
delete cues' files). Both destructive ops: double-confirm (type the patient `code`), audit-logged,
and a "back up first" reminder if no backup was made this session.

**0.6.2 — Clinician & clinic management.** Admin Center **Clinicians** page: edit display name
(`ClinicianRepo.update`), **disable/enable** (new `clinician.disabled` flag, migration v4; disabled
users can't log in), **delete** only when they own nothing, and **transfer patients** (reassign
`patient.created_by` from A to B; a confirmation lists affected patients; past `session.clinician_id`
preserved). **Clinic** page extends the profile: `clinic_address`, `clinic_email`, `clinic_phone`
(new `app_setting` keys) rendered in `report_screen._header_html`. All audit-logged.

**0.6.3 — Cross-patient & per-clinician reporting.** New repo queries: `PatientRepo.list_all()` /
`list_for_clinician(cid)`, `SessionRepo.list_for_clinician(cid)`, `list_all_finished()`. A **Reports**
page (and/or a "Cohort report" entry from the dashboard): **per-clinician filter** (dropdown),
**cohort summary CSV** (one row/patient: #sessions, mean %reduction, mean slope, last session,
via new `export.export_cohort_summary` composing `domain/reports.py` primitives), **cohort
aggregate PDF** (charts: mean habituation, %reduction distribution, end-reason mix — reuse the
`QPdfWriter`+`QTextDocument` machinery), and **clinician activity summary** (sessions/patients per
clinician over a date range). No PII beyond pseudonymous `code`.

**0.6.4 — App themes.** A `theme` setting (`light` default / `dark`) selected in Settings → User;
`ui/theme.py` loads `app.qss` or a new `app_dark.qss`; persisted to `app_setting` and applied at
startup and live on change. Dark palette mirrors the teal accent on dark surfaces; the immersive
cue background is already black.

---

## Open risks / notes
- **Restore on Windows** can hit file locks on the live DB → restore is *staging + restart*, never a
  hot swap. Documented in the restart prompt and the `admin_center` help topic.
- **Media in backups** can be large (video cues) — the backup zip may be big; show a size estimate
  and a progress-friendly (non-blocking where feasible) flow.
- Hard delete must also clean media on disk (cascade only covers DB rows).
- All new destructive/admin actions are **audit-logged** and **admin-key-gated**; nothing bypasses
  the existing PII export allowlist.
