"""Main window: navigation shell + the always-on panic button.

The panic button is a child of the window (a raised sibling of the screen stack),
so no screen or overlay can hide it. It is visible only while a session is active.
Esc triggers it too.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget

from ..domain.models import Clinician
from ..services.i18n import tr
from .context import AppContext
from .session_controller_factory import build_controller
from .widgets.panic_button import PanicButton

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


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.setWindowTitle(tr("app.title"))
        self.resize(1180, 760)
        self.setMinimumSize(960, 640)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self._current: Optional[QWidget] = None

        self.panic = PanicButton(self)
        self.panic.clicked.connect(self._on_panic)
        self._panic_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._panic_shortcut.activated.connect(self._on_panic)
        self._help_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F1), self)
        self._help_shortcut.activated.connect(self.show_help)

        self._active_controller = None
        self._active_exposure: Optional[ExposureScreen] = None

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

    def show_report(self, patient) -> None:
        self._set_panic_active(False)
        self._swap(ReportScreen(self, self.context, patient))

    def start_exposure(self, patient, substance: str, exposure_cues, positive_paths,
                       ambient_path=None, loop: bool = False) -> None:
        controller = build_controller(self.context, patient, substance, exposure_cues, loop=loop)
        screen = ExposureScreen(self, self.context, controller, positive_paths, ambient_path)
        self._active_controller = controller
        self._active_exposure = screen
        self._set_panic_active(True)
        self._swap(screen)

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
