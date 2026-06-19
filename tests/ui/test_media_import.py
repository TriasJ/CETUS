"""Batch media import (multi-file / folder) and enable-all/disable-all QoL."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from cravingcrave.config import AppConfig
from cravingcrave.domain.models import CueConfig, Patient
from cravingcrave.ui.context import AppContext
from cravingcrave.ui.screens import cue_config_screen as cc_mod
from cravingcrave.ui.screens.cue_config_screen import CueConfigScreen


class _FakeMessageBox:
    @staticmethod
    def information(*a, **k):
        return None

    @staticmethod
    def warning(*a, **k):
        return None


@pytest.fixture
def ctx(tmp_path, qapp):
    cfg = AppConfig(data_dir=tmp_path / "data", media_root=tmp_path / "media",
                    db_path=tmp_path / "data" / "cc.db")
    c = AppContext.create(cfg)
    c.clinician = c.auth.register("u", "U", "p")
    return c


def _img(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    im = QImage(20, 20, QImage.Format.Format_RGB32)
    im.fill(Qt.GlobalColor.blue)
    im.save(str(path))


def test_import_paths_copies_media_and_skips_non_media(ctx, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(cc_mod, "QMessageBox", _FakeMessageBox)
    p = ctx.repos.patients.create(Patient(code="PT1", primary_substance="meth", created_by=ctx.clinician.id))
    src = tmp_path / "incoming"
    _img(src / "a.png")
    _img(src / "b.png")
    (src / "notes.txt").write_text("not media")

    screen = CueConfigScreen(None, ctx, p)
    qtbot.addWidget(screen)
    screen._import_paths([str(src / "a.png"), str(src / "b.png"), str(src / "notes.txt")])

    cues = ctx.repos.cues.list_for_patient(p.id)
    assert len(cues) == 2                                   # txt skipped
    assert all(c.media_path.startswith("meth/") for c in cues)
    assert (Path(ctx.config.media_root) / "meth" / "a.png").exists()  # copied into library


def test_enable_disable_all(ctx, qtbot, monkeypatch):
    monkeypatch.setattr(cc_mod, "QMessageBox", _FakeMessageBox)
    p = ctx.repos.patients.create(Patient(code="PT2", primary_substance="meth", created_by=ctx.clinician.id))
    for i in range(3):
        ctx.repos.cues.create(CueConfig(patient_id=p.id, substance="meth",
                                        media_path=f"meth/{i}.png", media_type="image", appetitive_rank=i))
    screen = CueConfigScreen(None, ctx, p)
    qtbot.addWidget(screen)

    screen._set_all_enabled(False)
    assert all(not c.enabled for c in ctx.repos.cues.list_for_patient(p.id))
    screen._set_all_enabled(True)
    assert all(c.enabled for c in ctx.repos.cues.list_for_patient(p.id))
