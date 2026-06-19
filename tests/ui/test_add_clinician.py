"""In-app 'Agregar clínico' dialog: success + duplicate + mismatch + empty guards."""

import pytest

from cravingcrave.config import AppConfig
from cravingcrave.ui.context import AppContext
from cravingcrave.ui.screens import add_clinician_dialog as ac_mod
from cravingcrave.ui.screens.add_clinician_dialog import AddClinicianDialog


class _FakeMessageBox:
    def __init__(self):
        self.warnings: list[tuple] = []

    def warning(self, *a, **k):
        self.warnings.append(a)


@pytest.fixture
def ctx(tmp_path, qapp):
    cfg = AppConfig(data_dir=tmp_path / "data", media_root=tmp_path / "media",
                    db_path=tmp_path / "data" / "cc.db")
    c = AppContext.create(cfg)
    c.clinician = c.auth.register("AlanH", "Dr. Alan", "secret123")
    return c


def test_add_new_clinician_success(ctx, qtbot, monkeypatch):
    mb = _FakeMessageBox()
    monkeypatch.setattr(ac_mod, "QMessageBox", type("_MB", (), {"warning": staticmethod(mb.warning)}))
    dlg = AddClinicianDialog(ctx); qtbot.addWidget(dlg)
    dlg.username.setText("dra.ruiz")
    dlg.display_name.setText("Dra. Ana Ruiz")
    dlg.password.setText("nuevopass")
    dlg.confirm.setText("nuevopass")
    dlg._save()
    # The dialog accepted, the new clinician exists, and can log in.
    assert dlg.result() == AddClinicianDialog.DialogCode.Accepted
    assert ctx.auth.login("dra.ruiz", "nuevopass") is not None
    assert mb.warnings == []


def test_duplicate_username_blocked(ctx, qtbot, monkeypatch):
    mb = _FakeMessageBox()
    monkeypatch.setattr(ac_mod, "QMessageBox", type("_MB", (), {"warning": staticmethod(mb.warning)}))
    dlg = AddClinicianDialog(ctx); qtbot.addWidget(dlg)
    dlg.username.setText("AlanH")        # already exists from the fixture
    dlg.display_name.setText("Otro")
    dlg.password.setText("x"); dlg.confirm.setText("x")
    dlg._save()
    assert dlg.result() != AddClinicianDialog.DialogCode.Accepted
    assert len(mb.warnings) == 1                                   # duplicate warning shown
    assert ctx.auth.clinicians.count() == 1                         # nothing added


def test_password_mismatch_blocked(ctx, qtbot, monkeypatch):
    mb = _FakeMessageBox()
    monkeypatch.setattr(ac_mod, "QMessageBox", type("_MB", (), {"warning": staticmethod(mb.warning)}))
    dlg = AddClinicianDialog(ctx); qtbot.addWidget(dlg)
    dlg.username.setText("nueva"); dlg.password.setText("a"); dlg.confirm.setText("b")
    dlg._save()
    assert len(mb.warnings) == 1
    assert ctx.auth.clinicians.get_by_username("nueva") is None


def test_empty_fields_blocked(ctx, qtbot, monkeypatch):
    mb = _FakeMessageBox()
    monkeypatch.setattr(ac_mod, "QMessageBox", type("_MB", (), {"warning": staticmethod(mb.warning)}))
    dlg = AddClinicianDialog(ctx); qtbot.addWidget(dlg)
    dlg._save()                                                     # all empty
    assert len(mb.warnings) == 1
    assert ctx.auth.clinicians.count() == 1                         # unchanged
