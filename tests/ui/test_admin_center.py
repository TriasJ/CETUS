"""Admin Center (0.6.0): screen builds, audit repo, admin-key gate, migration v3."""

from pathlib import Path

from PySide6.QtWidgets import QDialog

from cravingcrave.config import AppConfig
from cravingcrave.data.database import Database
from cravingcrave.data.migrations import CURRENT_VERSION
from cravingcrave.domain.models import Patient
from cravingcrave.ui.context import AppContext
from cravingcrave.ui.main_window import MainWindow
from cravingcrave.ui.screens.admin_center_screen import AdminCenterScreen


def _ctx(tmp_path) -> AppContext:
    cfg = AppConfig(data_dir=tmp_path / "data", media_root=tmp_path / "media",
                    db_path=tmp_path / "data" / "cc.db")
    c = AppContext.create(cfg)
    c.clinician = c.auth.register("dra", "Dra", "pw123456")
    return c


def test_admin_center_builds_three_pages(tmp_path, qtbot):
    ctx = _ctx(tmp_path)
    ctx.repos.patients.create(Patient(code="PT01", primary_substance="meth",
                                      created_by=ctx.clinician.id))
    window = MainWindow(ctx); qtbot.addWidget(window)
    screen = AdminCenterScreen(window, ctx); qtbot.addWidget(screen)
    assert screen.nav.count() == 7          # Backup / Data / Clinicians / Clinic / Reports / Storage / Audit
    assert screen.stack.count() == 7
    assert screen.patient_combo.count() == 1   # Data page lists the seeded patient
    assert screen.clinician_list.count() == 1  # Clinicians page lists the seeded clinician
    # Storage counts reflect the seeded DB.
    assert ctx.repos.patients.count() == 1
    assert ctx.repos.clinicians.count() == 1


def test_show_admin_center_swaps_when_ungated(tmp_path, qtbot):
    ctx = _ctx(tmp_path)
    window = MainWindow(ctx); qtbot.addWidget(window); window.show_dashboard()
    window.show_admin_center(gated=False)
    assert isinstance(window._current, AdminCenterScreen)


def test_audit_repo_round_trip(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.repos.audit.log("backup_create", "cetus_backup.zip", "dra")
    ctx.repos.audit.log("backup_restore", "x.zip", "dra")
    recent = ctx.repos.audit.list_recent(10)
    assert recent[0]["action"] == "backup_restore"      # newest first
    assert recent[1]["action"] == "backup_create"
    assert recent[0]["actor"] == "dra"


def test_admin_gate_accepts_right_key_rejects_wrong(tmp_path, qtbot, monkeypatch):
    import cravingcrave.ui.widgets.admin_gate as gate
    monkeypatch.setattr(gate, "QMessageBox",
                        type("MB", (), {"warning": staticmethod(lambda *a, **k: None)}))
    ctx = _ctx(tmp_path)
    # Fresh DB → default admin key "cetus-admin" is active.
    ok = gate._AdminGateDialog(None, ctx); qtbot.addWidget(ok)
    ok.key_input.setText("cetus-admin"); ok._check()
    assert ok.result() == QDialog.DialogCode.Accepted

    bad = gate._AdminGateDialog(None, ctx); qtbot.addWidget(bad)
    bad.key_input.setText("wrong"); bad._check()
    assert bad.result() != QDialog.DialogCode.Accepted


def test_migration_v3_admin_audit_idempotent(tmp_path):
    db_path = tmp_path / "cc.db"
    db = Database(db_path); db.close()          # applies migrations to v3
    db2 = Database(db_path)                      # reopen: no-op re-apply
    try:
        row = db2.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='admin_audit'"
        ).fetchone()
        assert row is not None
        ver = db2.conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()[0]
        assert int(ver) == CURRENT_VERSION
    finally:
        db2.close()


def test_backup_bundle_file_exists_marker(tmp_path):
    # Sanity that the service module is importable and constants are stable for the UI.
    from cravingcrave.services import backup
    assert backup.MARKER == "cetus-backup"
    assert backup.DB_ARCNAME == "cravingcrave.db"
    assert Path(backup.MANIFEST_NAME).suffix == ".json"
