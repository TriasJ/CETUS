"""Hotkey registry + keyboard-only accessibility mode (event filter, VAS entry, rebinding)."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest

from cravingcrave.config import AppConfig
from cravingcrave.domain.models import CueConfig, Patient
from cravingcrave.session.session_controller import SessionController
from cravingcrave.ui import hotkeys
from cravingcrave.ui.context import AppContext
from cravingcrave.ui.main_window import MainWindow
from cravingcrave.ui.screens.exposure_screen import ExposureScreen

# ---------- registry (no Qt needed) ----------------------------------------

class _FakeSettings:
    def __init__(self, data=None):
        self._d = dict(data or {})

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


def test_default_bindings_match_registry():
    d = hotkeys.default_bindings()
    assert d["exposure.next_cue"] == "Right"
    assert d["access.axis_blur"] == "2"
    assert d["global.panic"] == "Esc"


def test_resolve_applies_override_and_falls_back():
    s = _FakeSettings({"hotkey.exposure.next_cue": "D"})
    resolved = hotkeys.resolve_bindings(s)
    assert resolved["exposure.next_cue"] == "D"          # override wins
    assert resolved["exposure.prev_cue"] == "Left"       # default retained


def test_reset_bindings_clears_overrides():
    s = _FakeSettings({"hotkey.exposure.next_cue": "D"})
    hotkeys.reset_bindings(s)
    assert hotkeys.resolve_bindings(s)["exposure.next_cue"] == "Right"


def test_panic_is_not_rebindable():
    panic = next(a for a in hotkeys.ACTIONS if a.id == "global.panic")
    assert panic.rebindable is False


# ---------- accessibility event filter -------------------------------------

def _make_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(50, 50, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.darkBlue)
    assert img.save(str(path))


def _ctx(tmp_path, **cfg) -> AppContext:
    config = AppConfig(data_dir=tmp_path / "data", media_root=tmp_path / "media",
                       db_path=tmp_path / "data" / "cc.db", **cfg)
    c = AppContext.create(config)
    c.clinician = c.auth.register("dra", "Dra", "pw123456")
    return c


def _exposure(ctx, qtbot, n_cues=3):
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    window.show()
    patient = ctx.repos.patients.create(Patient(code="PT-KB", primary_substance="meth",
                                                created_by=ctx.clinician.id))
    cues = []
    for i in range(n_cues):
        _make_image(Path(ctx.config.media_root) / "meth" / f"c{i}.png")
        cues.append(ctx.repos.cues.create(CueConfig(patient_id=patient.id, substance="meth",
                                                    media_path=f"meth/c{i}.png", media_type="image",
                                                    appetitive_rank=i)))
    controller = SessionController(ctx.repos, ctx.config, patient, ctx.clinician, "meth", cues)
    screen = ExposureScreen(window, ctx, controller, [])
    qtbot.addWidget(screen)
    window._active_exposure = screen
    window._active_controller = controller
    screen._ask_baseline()
    screen.vas_prompt.set_value(5)
    screen.vas_prompt.submit()   # baseline -> exposure begins at cue 0
    return window, screen, controller


def test_accessibility_mode_installs_filter_and_legend(tmp_path, qtbot):
    ctx = _ctx(tmp_path, accessibility_kbmode=True)
    _, screen, _ = _exposure(ctx, qtbot)
    assert screen._access_input is not None
    assert not screen.legend.isHidden()   # legend shown in accessibility mode
    assert screen._shortcuts == []   # no standard QShortcuts in accessibility mode


def test_arrows_change_cue_via_filter(tmp_path, qtbot):
    ctx = _ctx(tmp_path, accessibility_kbmode=True)
    _, screen, controller = _exposure(ctx, qtbot)
    assert controller.current_cue_index() == 0
    QTest.keyClick(screen, Qt.Key.Key_Right)
    assert controller.current_cue_index() == 1
    QTest.keyClick(screen, Qt.Key.Key_Left)
    assert controller.current_cue_index() == 0


def test_number_selects_axis_then_plus_minus_adjusts(tmp_path, qtbot):
    ctx = _ctx(tmp_path, accessibility_kbmode=True)
    _, screen, _ = _exposure(ctx, qtbot)
    # 2 selects blur, + increases it.
    QTest.keyClick(screen, Qt.Key.Key_2)
    before = screen.intensity.state()[1]
    QTest.keyClick(screen, Qt.Key.Key_Plus)
    assert screen.intensity.state()[1] > before      # blur increased
    # 3 selects dim, - would decrease from 0 -> clamps at 0 (no crash).
    QTest.keyClick(screen, Qt.Key.Key_3)
    QTest.keyClick(screen, Qt.Key.Key_Minus)
    assert screen.intensity.state()[2] == 0
    # 0 toggles mute.
    QTest.keyClick(screen, Qt.Key.Key_0)
    assert screen.intensity.state()[3] is True


def test_vas_keyboard_entry_and_submit(tmp_path, qtbot):
    ctx = _ctx(tmp_path, accessibility_kbmode=True)
    _, screen, controller = _exposure(ctx, qtbot)
    screen._mark_peak()                        # opens the VAS prompt (_prompt_open=True)
    assert screen._prompt_open
    QTest.keyClick(screen, Qt.Key.Key_7)       # digit sets the rating
    assert screen.vas_prompt.slider.value() == 7
    with qtbot.waitSignal(screen.vas_prompt.submitted, timeout=500):
        QTest.keyClick(screen, Qt.Key.Key_Return)   # Enter submits
    assert not screen._prompt_open             # submit cleared the prompt flag


def test_keyboard_mode_works_after_fullscreen_toggle(tmp_path, qtbot):
    # The filter lives on QApplication, so fullscreen (F11, a window-state change) does
    # not affect it — keyboard-only input stays usable in fullscreen/kiosk mode.
    ctx = _ctx(tmp_path, accessibility_kbmode=True)
    window, screen, controller = _exposure(ctx, qtbot)
    window._toggle_fullscreen()
    QTest.keyClick(screen, Qt.Key.Key_Right)
    assert controller.current_cue_index() == 1
    window._toggle_fullscreen()
    QTest.keyClick(screen, Qt.Key.Key_Right)
    assert controller.current_cue_index() == 2


def test_escape_not_consumed_by_filter(tmp_path, qtbot):
    ctx = _ctx(tmp_path, accessibility_kbmode=True)
    _, screen, _ = _exposure(ctx, qtbot)
    # The filter owns no Esc binding, so it returns False for Esc and the global panic
    # shortcut still fires (even over the VAS overlay).
    assert "Esc" not in screen._access_input._index


# ---------- rebinding persistence ------------------------------------------

def test_rebind_persists_and_conflict_rejected(tmp_path, qtbot, monkeypatch):
    import cravingcrave.ui.screens.settings_screen as ss
    from cravingcrave.ui.screens.settings_screen import SettingsScreen
    # Patch the modal warning up front (a real QMessageBox would block the test).
    monkeypatch.setattr(ss, "QMessageBox",
                        type("MB", (), {"warning": staticmethod(lambda *a, **k: None)}))
    ctx = _ctx(tmp_path)
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = SettingsScreen(window, ctx); qtbot.addWidget(screen)

    # "G" is unused by any exposure action -> accepted and persisted.
    screen._on_hotkey_captured("exposure.next_cue", "G")
    assert ctx.repos.settings.get("hotkey.exposure.next_cue") == "G"
    assert hotkeys.resolve_bindings(ctx.repos.settings)["exposure.next_cue"] == "G"

    # Conflict: prev_cue -> "G" (now used by next_cue, same scope) is rejected.
    screen._on_hotkey_captured("exposure.prev_cue", "G")
    assert hotkeys.resolve_bindings(ctx.repos.settings)["exposure.prev_cue"] == "Left"


def test_access_action_rejects_key_outside_keyset(tmp_path, qtbot, monkeypatch):
    import cravingcrave.ui.screens.settings_screen as ss
    from cravingcrave.ui.screens.settings_screen import SettingsScreen
    monkeypatch.setattr(ss, "QMessageBox",
                        type("MB", (), {"warning": staticmethod(lambda *a, **k: None)}))
    ctx = _ctx(tmp_path)
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = SettingsScreen(window, ctx); qtbot.addWidget(screen)
    screen._on_hotkey_captured("access.axis_blur", "T")   # letter -> rejected
    assert hotkeys.resolve_bindings(ctx.repos.settings)["access.axis_blur"] == "2"
