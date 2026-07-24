"""The in-app admin recovery dialog (Ctrl+Shift+A) lets a locked-out clinic recover."""

import pytest

from cravingcrave.config import AppConfig
from cravingcrave.ui.context import AppContext
from cravingcrave.ui.screens import admin_dialog as admin_mod
from cravingcrave.ui.screens.admin_dialog import AdminDialog
from cravingcrave.ui.screens.login_screen import LoginScreen


class _FakeMessageBox:
    @staticmethod
    def information(*a, **k):
        return None

    @staticmethod
    def warning(*a, **k):
        return None


@pytest.fixture
def context(tmp_path, qapp):
    cfg = AppConfig(data_dir=tmp_path / "data", media_root=tmp_path / "media",
                    db_path=tmp_path / "data" / "cc.db")
    ctx = AppContext.create(cfg)
    ctx.auth.register("AlanH", "Dr. Alan Hinojosa", "oldpass")
    return ctx


def test_wrong_admin_key_stays_locked(context, qtbot, monkeypatch):
    monkeypatch.setattr(admin_mod, "QMessageBox", _FakeMessageBox)
    dlg = AdminDialog(context)
    qtbot.addWidget(dlg)
    dlg.key_input.setText("not-the-key")
    dlg._check_key()
    assert dlg.stack.currentIndex() == 0  # never reached recovery page


def test_default_key_unlocks_and_resets_password(context, qtbot, monkeypatch):
    monkeypatch.setattr(admin_mod, "QMessageBox", _FakeMessageBox)
    monkeypatch.setattr(admin_mod, "QInputDialog",
                        type("QID", (), {"getText": staticmethod(lambda *a, **k: ("brandnew", True))}))
    dlg = AdminDialog(context)
    qtbot.addWidget(dlg)

    dlg.key_input.setText("cetus-admin")
    dlg._check_key()
    assert dlg.stack.currentIndex() == 1          # admin recovery page shown
    assert dlg.clinician_list.count() == 1

    dlg.clinician_list.setCurrentRow(0)
    dlg._reset_password()
    assert context.auth.login("AlanH", "oldpass") is None
    assert context.auth.login("AlanH", "brandnew") is not None


def test_login_screen_has_admin_shortcut(context, qtbot):
    screen = LoginScreen(window=None, context=context)
    qtbot.addWidget(screen)
    assert screen._admin_shortcut.key().toString() == "Ctrl+Shift+A"
