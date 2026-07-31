"""UX polish (0.5.0): tabbed Options, adaptive craving prompts, per-session Parameters
popup, and recursive add-from-folder."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from cravingcrave.config import AppConfig
from cravingcrave.domain.models import CueConfig, Patient
from cravingcrave.domain.uscs import USCS_STEPS
from cravingcrave.session.session_controller import SessionController
from cravingcrave.ui.context import AppContext
from cravingcrave.ui.main_window import MainWindow
from cravingcrave.ui.screens.cue_config_screen import CueConfigScreen
from cravingcrave.ui.screens.exposure_screen import ExposureScreen
from cravingcrave.ui.screens.session_setup_screen import SessionSetupScreen
from cravingcrave.ui.screens.settings_screen import SettingsScreen
from cravingcrave.ui.widgets.session_params_dialog import SessionParamsDialog


def _make_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(40, 40, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.darkCyan)
    assert img.save(str(path))


def _ctx(tmp_path, **cfg) -> AppContext:
    config = AppConfig(data_dir=tmp_path / "data", media_root=tmp_path / "media",
                       db_path=tmp_path / "data" / "cc.db", **cfg)
    c = AppContext.create(config)
    c.clinician = c.auth.register("dra", "Dra", "pw123456")
    return c


def _patient_with_cues(ctx, n=3):
    patient = ctx.repos.patients.create(Patient(code="PTX", primary_substance="meth",
                                                created_by=ctx.clinician.id))
    cues = []
    for i in range(n):
        _make_image(Path(ctx.config.media_root) / "meth" / f"cue{i}.png")
        cues.append(ctx.repos.cues.create(CueConfig(
            patient_id=patient.id, substance="meth", media_path=f"meth/cue{i}.png",
            media_type="image", appetitive_rank=i)))
    return patient, cues


def _exposure(ctx, qtbot):
    window = MainWindow(ctx); qtbot.addWidget(window)
    patient, cues = _patient_with_cues(ctx)
    controller = SessionController(ctx.repos, ctx.config, patient, ctx.clinician, "meth", cues)
    screen = ExposureScreen(window, ctx, controller, [])
    qtbot.addWidget(screen)
    screen._ask_baseline()
    screen.vas_prompt.set_value(6)
    screen.vas_prompt.submit()   # baseline -> exposure begins at cue 0
    return screen, controller


# ---------- immersive fullscreen -------------------------------------------

def test_immersive_mode_enter_exit(tmp_path, qtbot):
    ctx = _ctx(tmp_path)
    screen, _ = _exposure(ctx, qtbot)
    assert screen._immersive is False and not screen._right_box.isHidden()
    # Entering fullscreen hides the chart/sliders + top labels and floats the action bar.
    assert not screen.fs_reminder.isHidden()            # F11 reminder shown windowed
    screen.notify_fullscreen(True)
    assert screen._immersive is True
    assert screen._right_box.isHidden()
    assert screen.fs_reminder.isHidden()                # hidden once fullscreen
    assert not screen._bar_counter.isHidden()           # counter moves into the bar
    assert screen._actionbar.property("immersive") is True
    screen.on_user_activity()                            # reveal the auto-hiding bar
    assert not screen._actionbar.isHidden()
    # Leaving fullscreen restores the normal layout.
    screen.notify_fullscreen(False)
    assert screen._immersive is False
    assert not screen._right_box.isHidden()
    assert screen._bar_counter.isHidden()
    assert screen._actionbar.property("immersive") is False


# ---------- §1 tabbed Options ----------------------------------------------

def test_settings_builds_four_nav_pages(tmp_path, qtbot):
    ctx = _ctx(tmp_path)
    window = MainWindow(ctx); qtbot.addWidget(window)
    screen = SettingsScreen(window, ctx); qtbot.addWidget(screen)
    # Master-detail: an icon nav list drives a stacked set of pages.
    assert screen.nav.count() == 4
    assert screen.stack.count() == 4
    screen.nav.setCurrentRow(2)
    assert screen.stack.currentIndex() == 2
    # Advanced + clinical + contact widgets all exist regardless of which page they live on.
    for attr in ("vas_after_coping", "vas_every_n", "time_cap", "therapist", "lang_combo"):
        assert hasattr(screen, attr)


def test_settings_save_persists_advanced(tmp_path, qtbot, monkeypatch):
    import cravingcrave.ui.screens.settings_screen as ss
    monkeypatch.setattr(ss, "QMessageBox",
                        type("MB", (), {"information": staticmethod(lambda *a, **k: None)}))
    ctx = _ctx(tmp_path)
    window = MainWindow(ctx); qtbot.addWidget(window)
    screen = SettingsScreen(window, ctx); qtbot.addWidget(screen)
    screen.vas_after_coping.setChecked(True)
    screen.vas_every_n.setValue(3)
    screen._save()
    assert ctx.repos.settings.get("vas_prompt_after_coping") == "1"
    assert ctx.repos.settings.get("vas_prompt_every_n_cues") == "3"
    assert ctx.config.vas_prompt_after_coping is True
    assert ctx.config.vas_prompt_every_n_cues == 3


# ---------- §4 adaptive craving prompts ------------------------------------

def test_vas_prompt_after_coping_when_enabled(tmp_path, qtbot):
    ctx = _ctx(tmp_path, vas_prompt_after_coping=True)
    screen, _ = _exposure(ctx, qtbot)
    assert not screen._prompt_open
    screen._open_coping()
    for _ in range(len(USCS_STEPS)):     # walk the wizard to completion -> finished
        screen.coping_panel._advance()
    assert screen._prompt_open           # a craving VAS opened after coping


def test_no_vas_prompt_after_coping_when_disabled(tmp_path, qtbot):
    ctx = _ctx(tmp_path)                 # default False
    screen, _ = _exposure(ctx, qtbot)
    screen._open_coping()
    for _ in range(len(USCS_STEPS)):
        screen.coping_panel._advance()
    assert not screen._prompt_open


def test_vas_prompt_every_n_cues(tmp_path, qtbot):
    ctx = _ctx(tmp_path, vas_prompt_every_n_cues=2)
    screen, _ = _exposure(ctx, qtbot)
    screen._next_cue()                   # advance 1 -> no prompt yet
    assert not screen._prompt_open
    screen._next_cue()                   # advance 2 -> prompt
    assert screen._prompt_open


# ---------- §6 per-session Parameters popup --------------------------------

def test_params_dialog_seeds_and_overrides(qtbot):
    cfg = AppConfig(autoscroll_timed_seconds=7, accessibility_kbmode=True,
                    session_time_cap_seconds=600)
    dlg = SessionParamsDialog(None, cfg, random_order=True, loop=True); qtbot.addWidget(dlg)
    assert dlg.autoscroll_timed.value() == 7
    assert dlg.accessibility.isChecked() is True
    assert dlg.time_cap.value() == 10           # 600s shown as minutes
    assert dlg.wants_random() is True           # cue-ordering flags moved into the popup
    assert dlg.wants_loop() is True
    o = dlg.overrides()
    assert o["accessibility_kbmode"] is True
    assert o["session_time_cap_seconds"] == 600


def test_settings_persists_session_option_defaults(tmp_path, qtbot, monkeypatch):
    import cravingcrave.ui.screens.settings_screen as ss
    monkeypatch.setattr(ss, "QMessageBox",
                        type("MB", (), {"information": staticmethod(lambda *a, **k: None)}))
    ctx = _ctx(tmp_path)
    window = MainWindow(ctx); qtbot.addWidget(window)
    screen = SettingsScreen(window, ctx); qtbot.addWidget(screen)
    # Every Parameters option also lives in Ajustes as a default.
    screen.default_random_order.setChecked(True)
    screen.default_start_fullscreen.setChecked(True)
    screen._save()
    assert ctx.repos.settings.get("default_random_order") == "1"
    assert ctx.repos.settings.get("default_start_fullscreen") == "1"
    assert ctx.config.default_random_order is True


def test_setup_seeds_from_config_defaults_and_remembers_last(tmp_path, qtbot):
    ctx = _ctx(tmp_path, default_random_order=True, default_loop=False)
    patient, _ = _patient_with_cues(ctx)
    window = MainWindow(ctx); qtbot.addWidget(window)
    # A fresh patient's setup seeds run flags from the clinic-wide config defaults.
    s1 = SessionSetupScreen(window, ctx, patient); qtbot.addWidget(s1)
    assert s1._random_order is True and s1._loop is False
    assert s1._params_customized is False
    # Customising + persisting -> a new setup for the SAME patient remembers the last config.
    s1._param_overrides = {"accessibility_kbmode": True}
    s1._loop = True
    s1._persist_last_params()
    s2 = SessionSetupScreen(window, ctx, patient); qtbot.addWidget(s2)
    assert s2._loop is True
    assert s2._params_customized is True
    assert s2._param_overrides["accessibility_kbmode"] is True


def test_start_exposure_applies_overrides_without_mutating_global(tmp_path, qtbot):
    ctx = _ctx(tmp_path)
    patient, cues = _patient_with_cues(ctx)
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    assert ctx.config.accessibility_kbmode is False
    window.start_exposure(patient, "meth", cues, [],
                          overrides={"accessibility_kbmode": True,
                                     "session_time_cap_seconds": 300})
    screen = window._active_exposure
    assert screen.context.config.accessibility_kbmode is True
    assert screen.controller.config.session_time_cap_seconds == 300
    # Global (clinic-wide) config is untouched.
    assert ctx.config.accessibility_kbmode is False
    assert ctx.config.session_time_cap_seconds != 300


# ---------- §2 recursive add-from-folder -----------------------------------

def test_add_folder_recurses_into_subfolders(tmp_path, qtbot, monkeypatch):
    import cravingcrave.ui.screens.cue_config_screen as ccs
    ctx = _ctx(tmp_path)
    patient = ctx.repos.patients.create(Patient(code="PTF", primary_substance="meth",
                                                created_by=ctx.clinician.id))
    window = MainWindow(ctx); qtbot.addWidget(window)
    screen = CueConfigScreen(window, ctx, patient); qtbot.addWidget(screen)

    src = tmp_path / "src"
    _make_image(src / "a.png")
    _make_image(src / "sub" / "b.png")   # nested one folder deep
    monkeypatch.setattr(ccs.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: str(src)))
    monkeypatch.setattr(ccs.QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    screen._add_folder()

    names = {c.media_path.split("/")[-1] for c in ctx.repos.cues.list_for_patient(patient.id)}
    assert {"a.png", "b.png"} <= names   # the subfolder file was imported too
