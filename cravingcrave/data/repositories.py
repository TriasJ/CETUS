"""Repositories: the only place that knows SQL. UI and domain never touch sqlite.

Each repo wraps a ``Database`` and maps between rows and the dataclasses in
``domain.models``. Booleans are stored as 0/1 integers.
"""

from __future__ import annotations

import sqlite3

from ..domain.models import (
    Clinician,
    CopingEvent,
    CravingRating,
    CueConfig,
    CueDwell,
    IntensityEvent,
    Patient,
    Session,
    utc_now_iso,
)
from .database import Database


def _b(value) -> bool:
    return bool(value)


class ClinicianRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, c: Clinician) -> Clinician:
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO clinician (username, display_name, password_hash, created_at) "
                "VALUES (?,?,?,?)",
                (c.username, c.display_name, c.password_hash, c.created_at),
            )
            c.id = cur.lastrowid
        return c

    def get_by_username(self, username: str) -> Clinician | None:
        row = self.db.conn.execute(
            "SELECT * FROM clinician WHERE username = ?", (username,)
        ).fetchone()
        return self._row(row) if row else None

    def count(self) -> int:
        return int(self.db.conn.execute("SELECT COUNT(*) FROM clinician").fetchone()[0])

    def list_all(self) -> list[Clinician]:
        rows = self.db.conn.execute("SELECT * FROM clinician ORDER BY username").fetchall()
        return [self._row(r) for r in rows]

    def update_password(self, clinician_id: int, password_hash: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE clinician SET password_hash = ? WHERE id = ?",
                         (password_hash, clinician_id))

    def set_display_name(self, clinician_id: int, display_name: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE clinician SET display_name = ? WHERE id = ?",
                         (display_name, clinician_id))

    def set_disabled(self, clinician_id: int, disabled: bool) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE clinician SET disabled = ? WHERE id = ?",
                         (int(disabled), clinician_id))

    def delete(self, clinician_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM clinician WHERE id = ?", (clinician_id,))

    def owns_counts(self, clinician_id: int) -> tuple[int, int]:
        """(patients created by, sessions run by) — used to guard hard delete."""
        pats = self.db.conn.execute(
            "SELECT COUNT(*) FROM patient WHERE created_by = ?", (clinician_id,)).fetchone()[0]
        sess = self.db.conn.execute(
            "SELECT COUNT(*) FROM session WHERE clinician_id = ?", (clinician_id,)).fetchone()[0]
        return int(pats), int(sess)

    @staticmethod
    def _row(r: sqlite3.Row) -> Clinician:
        return Clinician(
            id=r["id"],
            username=r["username"],
            display_name=r["display_name"],
            password_hash=r["password_hash"],
            created_at=r["created_at"],
            disabled=_b(r["disabled"]),
        )


class PatientRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, p: Patient) -> Patient:
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO patient (code, display_name, birth_year, primary_substance, "
                "notes, created_by, created_at, archived) VALUES (?,?,?,?,?,?,?,?)",
                (
                    p.code, p.display_name, p.birth_year, p.primary_substance,
                    p.notes, p.created_by, p.created_at, int(p.archived),
                ),
            )
            p.id = cur.lastrowid
        return p

    def get(self, patient_id: int) -> Patient | None:
        row = self.db.conn.execute(
            "SELECT * FROM patient WHERE id = ?", (patient_id,)
        ).fetchone()
        return self._row(row) if row else None

    def count(self) -> int:
        return int(self.db.conn.execute("SELECT COUNT(*) FROM patient").fetchone()[0])

    def list_active(self) -> list[Patient]:
        rows = self.db.conn.execute(
            "SELECT * FROM patient WHERE archived = 0 ORDER BY code"
        ).fetchall()
        return [self._row(r) for r in rows]

    def list_all(self) -> list[Patient]:
        """Every patient, including archived (for admin data-handling tools)."""
        rows = self.db.conn.execute("SELECT * FROM patient ORDER BY code").fetchall()
        return [self._row(r) for r in rows]

    def list_for_clinician(self, clinician_id: int) -> list[Patient]:
        """Patients owned (created) by a clinician — for per-clinician cohort reports."""
        rows = self.db.conn.execute(
            "SELECT * FROM patient WHERE created_by = ? ORDER BY code", (clinician_id,)).fetchall()
        return [self._row(r) for r in rows]

    def anonymize(self, patient_id: int) -> None:
        """Strip PII (name/birth year/notes), keeping the pseudonymous code + all sessions."""
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE patient SET display_name = NULL, birth_year = NULL, notes = NULL "
                "WHERE id = ?", (patient_id,))

    def delete(self, patient_id: int) -> None:
        """Hard delete a patient; ON DELETE CASCADE removes cues, sessions and their events."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM patient WHERE id = ?", (patient_id,))

    def reassign_owner(self, from_clinician_id: int, to_clinician_id: int) -> int:
        """Transfer patient ownership (created_by) between clinicians. Returns rows moved.

        Past ``session.clinician_id`` values are left intact as the historical record."""
        with self.db.transaction() as conn:
            cur = conn.execute("UPDATE patient SET created_by = ? WHERE created_by = ?",
                               (to_clinician_id, from_clinician_id))
            return cur.rowcount

    def count_for_owner(self, clinician_id: int) -> int:
        return int(self.db.conn.execute(
            "SELECT COUNT(*) FROM patient WHERE created_by = ?", (clinician_id,)).fetchone()[0])

    def update(self, p: Patient) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE patient SET code=?, display_name=?, birth_year=?, primary_substance=?, "
                "notes=?, archived=? WHERE id=?",
                (
                    p.code, p.display_name, p.birth_year, p.primary_substance,
                    p.notes, int(p.archived), p.id,
                ),
            )

    @staticmethod
    def _row(r: sqlite3.Row) -> Patient:
        return Patient(
            id=r["id"], code=r["code"], display_name=r["display_name"],
            birth_year=r["birth_year"], primary_substance=r["primary_substance"],
            notes=r["notes"], created_by=r["created_by"], created_at=r["created_at"],
            archived=_b(r["archived"]),
        )


class CueConfigRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, c: CueConfig) -> CueConfig:
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO cue_config (patient_id, substance, media_path, media_type, "
                "appetitive_rank, enabled, is_personal_reason, is_neutral, craving_weight, "
                "created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    c.patient_id, c.substance, c.media_path, c.media_type,
                    c.appetitive_rank, int(c.enabled), int(c.is_personal_reason),
                    int(c.is_neutral), c.craving_weight, c.created_at,
                ),
            )
            c.id = cur.lastrowid
        return c

    def list_for_patient(self, patient_id: int) -> list[CueConfig]:
        rows = self.db.conn.execute(
            "SELECT * FROM cue_config WHERE patient_id = ? ORDER BY appetitive_rank, id",
            (patient_id,),
        ).fetchall()
        return [self._row(r) for r in rows]

    def delete(self, cue_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM cue_config WHERE id = ?", (cue_id,))

    def update(self, c: CueConfig) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE cue_config SET substance=?, media_path=?, media_type=?, "
                "appetitive_rank=?, enabled=?, is_personal_reason=?, is_neutral=?, "
                "craving_weight=? WHERE id=?",
                (
                    c.substance, c.media_path, c.media_type, c.appetitive_rank,
                    int(c.enabled), int(c.is_personal_reason), int(c.is_neutral),
                    c.craving_weight, c.id,
                ),
            )

    @staticmethod
    def _row(r: sqlite3.Row) -> CueConfig:
        keys = r.keys()
        return CueConfig(
            id=r["id"], patient_id=r["patient_id"], substance=r["substance"],
            media_path=r["media_path"], media_type=r["media_type"],
            appetitive_rank=r["appetitive_rank"], enabled=_b(r["enabled"]),
            is_personal_reason=_b(r["is_personal_reason"]),
            is_neutral=_b(r["is_neutral"]) if "is_neutral" in keys else False,
            craving_weight=r["craving_weight"] if "craving_weight" in keys else None,
            created_at=r["created_at"],
        )


class SessionRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, s: Session) -> Session:
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO session (patient_id, clinician_id, substance, started_at, "
                "consent_given, app_version, mode) VALUES (?,?,?,?,?,?,?)",
                (s.patient_id, s.clinician_id, s.substance, s.started_at,
                 int(s.consent_given), s.app_version, s.mode),
            )
            s.id = cur.lastrowid
        return s

    def finalize(self, s: Session) -> None:
        """Write end-of-session fields (end_reason, VAS summary, slope)."""
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE session SET ended_at=?, end_reason=?, baseline_vas=?, peak_vas=?, "
                "endpoint_vas=?, habituation_slope=? WHERE id=?",
                (s.ended_at, s.end_reason, s.baseline_vas, s.peak_vas,
                 s.endpoint_vas, s.habituation_slope, s.id),
            )

    def update_notes(self, session_id: int, notes: str | None) -> None:
        """Set/clear the clinician's free-text notes for a session (post-hoc edit)."""
        with self.db.transaction() as conn:
            conn.execute("UPDATE session SET clinician_notes = ? WHERE id = ?",
                         (notes, session_id))

    def get(self, session_id: int) -> Session | None:
        row = self.db.conn.execute(
            "SELECT * FROM session WHERE id = ?", (session_id,)
        ).fetchone()
        return self._row(row) if row else None

    def list_for_patient(self, patient_id: int) -> list[Session]:
        rows = self.db.conn.execute(
            "SELECT * FROM session WHERE patient_id = ? ORDER BY started_at", (patient_id,)
        ).fetchall()
        return [self._row(r) for r in rows]

    def count(self) -> int:
        return int(self.db.conn.execute("SELECT COUNT(*) FROM session").fetchone()[0])

    def list_for_clinician(self, clinician_id: int) -> list[Session]:
        rows = self.db.conn.execute(
            "SELECT * FROM session WHERE clinician_id = ? ORDER BY started_at",
            (clinician_id,)).fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(r: sqlite3.Row) -> Session:
        keys = r.keys()
        return Session(
            id=r["id"], patient_id=r["patient_id"], clinician_id=r["clinician_id"],
            substance=r["substance"], started_at=r["started_at"], ended_at=r["ended_at"],
            end_reason=r["end_reason"], consent_given=_b(r["consent_given"]),
            baseline_vas=r["baseline_vas"], peak_vas=r["peak_vas"],
            endpoint_vas=r["endpoint_vas"], habituation_slope=r["habituation_slope"],
            app_version=r["app_version"],
            clinician_notes=r["clinician_notes"] if "clinician_notes" in keys else None,
            mode=r["mode"] if "mode" in keys else "intense",
        )


class CravingRatingRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, r: CravingRating) -> CravingRating:
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO craving_rating (session_id, ts, elapsed_sec, value, kind, cue_config_id) "
                "VALUES (?,?,?,?,?,?)",
                (r.session_id, r.ts, r.elapsed_sec, r.value, r.kind, r.cue_config_id),
            )
            r.id = cur.lastrowid
        return r

    def list_for_session(self, session_id: int) -> list[CravingRating]:
        rows = self.db.conn.execute(
            "SELECT * FROM craving_rating WHERE session_id = ? ORDER BY elapsed_sec, id",
            (session_id,),
        ).fetchall()
        return [self._row(r) for r in rows]

    def list_for_patient(self, patient_id: int) -> list[CravingRating]:
        """Every craving rating for a patient across all sessions (cross-session per-cue work)."""
        rows = self.db.conn.execute(
            "SELECT c.* FROM craving_rating c JOIN session s ON c.session_id = s.id "
            "WHERE s.patient_id = ? ORDER BY c.session_id, c.elapsed_sec, c.id",
            (patient_id,),
        ).fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(r: sqlite3.Row) -> CravingRating:
        return CravingRating(
            id=r["id"], session_id=r["session_id"], ts=r["ts"],
            elapsed_sec=r["elapsed_sec"], value=r["value"], kind=r["kind"],
            cue_config_id=r["cue_config_id"],
        )


class CopingEventRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, e: CopingEvent) -> CopingEvent:
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO coping_event (session_id, ts, elapsed_sec, skill, detail) "
                "VALUES (?,?,?,?,?)",
                (e.session_id, e.ts, e.elapsed_sec, e.skill, e.detail),
            )
            e.id = cur.lastrowid
        return e

    def list_for_session(self, session_id: int) -> list[CopingEvent]:
        rows = self.db.conn.execute(
            "SELECT * FROM coping_event WHERE session_id = ? ORDER BY elapsed_sec, id",
            (session_id,),
        ).fetchall()
        return [
            CopingEvent(
                id=r["id"], session_id=r["session_id"], ts=r["ts"],
                elapsed_sec=r["elapsed_sec"], skill=r["skill"], detail=r["detail"],
            )
            for r in rows
        ]

    def list_for_patient(self, patient_id: int) -> list[CopingEvent]:
        """Every coping response for a patient across all sessions (for export)."""
        rows = self.db.conn.execute(
            "SELECT c.* FROM coping_event c JOIN session s ON c.session_id = s.id "
            "WHERE s.patient_id = ? ORDER BY c.session_id, c.elapsed_sec, c.id",
            (patient_id,),
        ).fetchall()
        return [
            CopingEvent(
                id=r["id"], session_id=r["session_id"], ts=r["ts"],
                elapsed_sec=r["elapsed_sec"], skill=r["skill"], detail=r["detail"],
            )
            for r in rows
        ]


class IntensityEventRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, e: IntensityEvent) -> IntensityEvent:
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO intensity_event (session_id, ts, elapsed_sec, action, "
                "scale_pct, blur_pct, dim_pct, muted) VALUES (?,?,?,?,?,?,?,?)",
                (e.session_id, e.ts, e.elapsed_sec, e.action, e.scale_pct,
                 e.blur_pct, e.dim_pct, None if e.muted is None else int(e.muted)),
            )
            e.id = cur.lastrowid
        return e

    def list_for_session(self, session_id: int) -> list[IntensityEvent]:
        rows = self.db.conn.execute(
            "SELECT * FROM intensity_event WHERE session_id = ? ORDER BY elapsed_sec, id",
            (session_id,),
        ).fetchall()
        return [
            IntensityEvent(
                id=r["id"], session_id=r["session_id"], ts=r["ts"],
                elapsed_sec=r["elapsed_sec"], action=r["action"], scale_pct=r["scale_pct"],
                blur_pct=r["blur_pct"], dim_pct=r["dim_pct"],
                muted=None if r["muted"] is None else _b(r["muted"]),
            )
            for r in rows
        ]


class CueDwellRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, d: CueDwell) -> CueDwell:
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO cue_dwell (session_id, cue_config_id, start_sec, end_sec, dwell_sec) "
                "VALUES (?,?,?,?,?)",
                (d.session_id, d.cue_config_id, d.start_sec, d.end_sec, d.dwell_sec),
            )
            d.id = cur.lastrowid
        return d

    def list_for_session(self, session_id: int) -> list[CueDwell]:
        rows = self.db.conn.execute(
            "SELECT * FROM cue_dwell WHERE session_id = ? ORDER BY start_sec, id",
            (session_id,),
        ).fetchall()
        return [self._row(r) for r in rows]

    def list_for_patient(self, patient_id: int) -> list[CueDwell]:
        """Every cue dwell for a patient across all sessions (for cross-session analysis)."""
        rows = self.db.conn.execute(
            "SELECT d.* FROM cue_dwell d JOIN session s ON d.session_id = s.id "
            "WHERE s.patient_id = ? ORDER BY d.session_id, d.start_sec, d.id",
            (patient_id,),
        ).fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(r: sqlite3.Row) -> CueDwell:
        return CueDwell(
            id=r["id"], session_id=r["session_id"], cue_config_id=r["cue_config_id"],
            start_sec=r["start_sec"], end_sec=r["end_sec"], dwell_sec=r["dwell_sec"],
        )


class SettingRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get(self, key: str, default: str | None = None) -> str | None:
        row = self.db.conn.execute(
            "SELECT value FROM app_setting WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else default

    def set(self, key: str, value: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO app_setting (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )


class AuditRepo:
    """Admin action log (key changes, backups, restores, deletes). Newest-first read."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def log(self, action: str, detail: str = "", actor: str = "") -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO admin_audit (ts, actor, action, detail) VALUES (?,?,?,?)",
                (utc_now_iso(), actor, action, detail),
            )

    def list_recent(self, limit: int = 200) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT ts, actor, action, detail FROM admin_audit ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"ts": r["ts"], "actor": r["actor"], "action": r["action"], "detail": r["detail"]}
            for r in rows
        ]


class Repositories:
    """Convenience bundle wiring every repo to one Database."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.clinicians = ClinicianRepo(db)
        self.patients = PatientRepo(db)
        self.cues = CueConfigRepo(db)
        self.sessions = SessionRepo(db)
        self.ratings = CravingRatingRepo(db)
        self.coping = CopingEventRepo(db)
        self.intensity = IntensityEventRepo(db)
        self.cue_dwell = CueDwellRepo(db)
        self.settings = SettingRepo(db)
        self.audit = AuditRepo(db)
