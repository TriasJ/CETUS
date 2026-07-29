"""Main window: navigation shell + the always-on panic button.

The panic button is a child of the window (a raised sibling of the screen stack),
so no screen or overlay can hide it. It is visible only while a session is active.
Esc triggers it too.
"""

from __future__ import annotations

import dataclasses

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget, QWidget

from ..services.i18n import current_locale, set_locale, tr
from . import hotkeys
from .context import AppContext
from .screens.calm_screen import CalmScreen
from .screens.cue_config_screen import CueConfigScreen
from .screens.dashboard_screen import DashboardScreen
from .screens.exposure_screen import ExposureScreen
from .screens.help_dialog import HelpDialog
from .screens.login_screen import LoginScreen
from .screens.patient_screen import PatientScreen
from .screens.report_screen import ReportScreen
from .screens.session_setup_screen import SessionSetupScreen
from .screens.settings_screen import SettingsScreen
from .screens.summary_screen import SummaryScreen
from .session_controller_factory import build_controller
from .widgets.panic_button import PanicButton


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.setWindowTitle(tr("app.title"))
        self.resize(1180, 760)
        self.setMinimumSize(960, 640)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self._current: QWidget | None = None

        self.panic = PanicButton(self)
        self.panic.clicked.connect(self._on_panic)
        # Global shortcuts are built from the (rebindable) hotkey registry.
        self._global_shortcuts: dict[str, QShortcut] = {}
        self.reload_global_hotkeys()

        self._active_controller = None
        self._active_exposure: ExposureScreen | None = None

        self.show_login()

    # --- navigation helpers -------------------------------------------------
    def _swap(self, widget: QWidget) -> None:
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)
        if self._current is not None:
            self.stack.removeWidget(self._current)
            self._current.deleteLater()
        self._current = widget
        self.panic.raise_()

    def _set_panic_active(self, active: bool) -> None:
        self.panic.setVisible(active)
        if active:
            self._position_panic()
            self.panic.raise_()

    # --- screens ------------------------------------------------------------
    def show_login(self) -> None:
        self._active_controller = None
        self._active_exposure = None
        self._set_panic_active(False)
        self._swap(LoginScreen(self, self.context))

    def show_dashboard(self) -> None:
        self._active_controller = None
        self._active_exposure = None
        self._set_panic_active(False)
        self._swap(DashboardScreen(self, self.context))

    def show_patient(self, patient_id: int) -> None:
        self._set_panic_active(False)
        self._swap(PatientScreen(self, self.context, patient_id))

    def show_cue_config(self, patient) -> None:
        self._swap(CueConfigScreen(self, self.context, patient))

    def show_session_setup(self, patient) -> None:
        self._swap(SessionSetupScreen(self, self.context, patient))

    def show_settings(self) -> None:
        self._swap(SettingsScreen(self, self.context))

    def show_help(self) -> None:
        HelpDialog(self).exec()

    def reload_global_hotkeys(self) -> None:
        """(Re)build the window-level shortcuts from the resolved registry bindings, so a
        rebind in Settings applies live without a restart. Panic (Esc) stays bound here so
        it always fires, even over the exposure overlays and in accessibility mode."""
        for sc in self._global_shortcuts.values():
            sc.setParent(None)
        self._global_shortcuts.clear()
        resolved = hotkeys.resolve_bindings(self.context.repos.settings)
        slots = {
            "global.panic": self._on_panic,
            "global.help": self.show_help,
            "global.fullscreen": self._toggle_fullscreen,
        }
        for act in hotkeys.actions_in(hotkeys.Scope.GLOBAL):
            sc = QShortcut(QKeySequence(resolved[act.id]), self)
            sc.activated.connect(slots[act.id])
            self._global_shortcuts[act.id] = sc
        # Keep named handles for tests / clarity.
        self._panic_shortcut = self._global_shortcuts["global.panic"]
        self._help_shortcut = self._global_shortcuts["global.help"]
        self._fullscreen_shortcut = self._global_shortcuts["global.fullscreen"]

    def change_language(self, locale: str, redisplay=None) -> None:
        """Switch the UI language live: persist the choice, reload i18n, refresh the
        window title, and re-render the current screen so every ``tr()`` re-evaluates.

        ``redisplay`` is the caller's own show_* method (e.g. ``self.window.show_settings``)
        so the active screen rebuilds in place in the new language without a restart."""
        if not locale or locale == current_locale():
            return
        self.context.repos.settings.set("locale", locale)
        self.context.config.locale = locale
        set_locale(locale)
        self.setWindowTitle(tr("app.title"))
        if redisplay is not None:
            redisplay()

    def _toggle_fullscreen(self) -> None:
        """F11: toggle fullscreen. The panic overlay re-anchors via resizeEvent, so no
        extra repositioning is needed. Esc remains dedicated to the ALTO panic button."""
        if self.isFullScreen():
            self.showNormal()
            full = False
        else:
            self.showFullScreen()
            full = True
        if self._active_exposure is not None:
            self._active_exposure.notify_fullscreen(full)

    def show_report(self, patient) -> None:
        self._set_panic_active(False)
        self._swap(ReportScreen(self, self.context, patient))

    def start_exposure(self, patient, substance: str, exposure_cues, positive_paths,
                       ambient_path=None, loop: bool = False, overrides: dict | None = None,
                       start_fullscreen: bool = False) -> None:
        # Defense-in-depth: never enter EXPOSURE against a blank cue surface, even if a
        # caller bypasses the session-setup gate.
        if not exposure_cues:
            QMessageBox.warning(self, tr("app.title"), tr("setup.no_cues"))
            return
        # Per-session parameter overrides apply to a run-only copy of the context, so the
        # clinic-wide (global) config is never mutated.
        run_ctx = self.context
        if overrides:
            run_ctx = dataclasses.replace(
                self.context, config=dataclasses.replace(self.context.config, **overrides))
        controller = build_controller(run_ctx, patient, substance, exposure_cues, loop=loop)
        screen = ExposureScreen(self, run_ctx, controller, positive_paths, ambient_path)
        self._active_controller = controller
        self._active_exposure = screen
        self._set_panic_active(True)
        self._swap(screen)
        if start_fullscreen and not self.isFullScreen():
            self.showFullScreen()
            screen.notify_fullscreen(True)

    def show_summary(self, session, controller) -> None:
        self._active_controller = None
        self._active_exposure = None
        self._set_panic_active(False)
        patient = self.context.repos.patients.get(session.patient_id)
        self._swap(SummaryScreen(self, self.context, session, patient))

    def show_calm(self) -> None:
        self._set_panic_active(False)
        self._swap(CalmScreen(self, self.context))

    # --- panic --------------------------------------------------------------
    def _on_panic(self) -> None:
        if not self.panic.isVisible() or self._active_controller is None:
            return
        if self._active_exposure is not None:
            self._active_exposure.stop_timers()
        self._active_controller.panic()
        self._active_controller = None
        self._active_exposure = None
        self.show_calm()

    # --- geometry -----------------------------------------------------------
    def _position_panic(self) -> None:
        self.panic.adjustSize()
        self.panic.move(self.width() - self.panic.width() - 24, 18)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_panic()
        self.panic.raise_()
