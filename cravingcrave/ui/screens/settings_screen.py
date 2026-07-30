"""Clinic settings: safety contacts and clinical parameters (persisted to app_setting).

Master-detail layout: an icon navigation list on the left switches a QStackedWidget of
grouped pages on the right (Session / User / Hotkeys / Substances), with a persistent Save
bar. Sections are QGroupBoxes for a compact, grouped look.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...services import substances as subs
from ...services.crisis import CrisisInfo
from ...services.i18n import available_locales, current_locale, tr
from .. import hotkeys
from ..context import AppContext
from ..widgets.key_capture_button import KeyCaptureButton

_NAV_INK = "#2f5d63"       # dark teal for an unselected row (on white)
_NAV_INK_SELECTED = "#ffffff"   # white for the selected row (on the teal highlight)


def _draw_nav_icon(kind: str, ink: str = _NAV_INK) -> QIcon:
    """Draw a simple vector pictograph (no font/emoji dependency, renders everywhere)."""
    pm = QPixmap(24, 24)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(ink)
    p.setPen(QPen(c, 2))
    p.setBrush(QBrush(c))
    if kind == "session":                       # play triangle
        p.drawPolygon(QPolygon([QPoint(8, 5), QPoint(8, 19), QPoint(19, 12)]))
    elif kind == "user":                        # head + shoulders
        p.drawEllipse(QPoint(12, 8), 4, 4)
        p.drawRoundedRect(QRectF(5.5, 14, 13, 8), 4, 4)
    elif kind == "hotkeys":                      # keyboard outline + keys
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(3.5, 7.5, 17, 10), 2, 2)
        p.setBrush(QBrush(c)); p.setPen(Qt.PenStyle.NoPen)
        for x in (7, 12, 17):
            p.drawEllipse(QPoint(x, 11), 1, 1)
        for x in (9, 15):
            p.drawEllipse(QPoint(x, 14), 1, 1)
    elif kind == "substances":                   # flask / beaker
        p.drawPolygon(QPolygon([QPoint(10, 3), QPoint(14, 3), QPoint(14, 9),
                                QPoint(19, 20), QPoint(5, 20), QPoint(10, 9)]))
    elif kind == "backup":                        # archive box + lid line
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(4, 8, 16, 12), 2, 2)
        p.drawLine(4, 12, 20, 12)
        p.drawLine(10, 12, 10, 8); p.drawLine(14, 12, 14, 8)
    elif kind == "storage":                       # disk cylinder
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(5, 4, 14, 5))
        p.drawLine(5, 6, 5, 18); p.drawLine(19, 6, 19, 18)
        p.drawArc(QRectF(5, 13, 14, 5), 0, -180 * 16)
    elif kind == "audit":                         # log lines
        p.setPen(QPen(c, 2))
        for y in (7, 12, 17):
            p.drawLine(5, y, 19, y)
    elif kind == "data":                          # ID card: head + text lines
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(3.5, 6, 17, 12), 2, 2)
        p.setBrush(QBrush(c))
        p.drawEllipse(QPoint(9, 11), 2, 2)
        p.setPen(QPen(c, 1))
        p.drawLine(13, 10, 18, 10); p.drawLine(13, 13, 18, 13)
    p.end()
    return QIcon(pm)


class SettingsScreen(QWidget):
    def __init__(self, window, context: AppContext) -> None:
        super().__init__()
        self.window = window
        self.context = context
        cfg = context.config
        info = context.crisis.get()

        back = QPushButton(tr("common.back"))
        back.clicked.connect(window.show_dashboard)
        title = QLabel(tr("settings.title"))
        title.setObjectName("H1")
        help_btn = QPushButton(tr("common.help"))
        help_btn.clicked.connect(lambda: self.window.show_help("settings_help"))
        header = QHBoxLayout()
        header.addWidget(back); header.addSpacing(10); header.addWidget(title)
        header.addStretch(1); header.addWidget(help_btn)

        # Contact + clinical widgets are created here so `_save` can read them regardless of
        # which page they end up on.
        self.therapist = QLineEdit(info.therapist_phone)
        self.crisis = QLineEdit(info.crisis_line)
        self.emergency = QLineEdit(info.emergency_number)

        self.time_cap = QSpinBox(); self.time_cap.setRange(1, 120); self.time_cap.setSuffix(" min")
        self.time_cap.setValue(cfg.session_time_cap_seconds // 60)
        self.periodic = QSpinBox(); self.periodic.setRange(5, 300); self.periodic.setSuffix(" s")
        self.periodic.setValue(cfg.periodic_vas_seconds)
        self.threshold = QSpinBox(); self.threshold.setRange(0, cfg.vas_max)
        self.threshold.setValue(cfg.habituation_threshold)
        self.consecutive = QSpinBox(); self.consecutive.setRange(1, 10)
        self.consecutive.setValue(cfg.habituation_consecutive)

        # Left navigation (icons) drives the right-hand stacked pages.
        self.nav = QListWidget(); self.nav.setObjectName("SettingsNav")
        self.nav.setFixedWidth(200)
        self.nav.setIconSize(QSize(24, 24))
        self.nav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.stack = QStackedWidget()
        specs = [
            ("session", "settings.tab_session", self._session_page()),
            ("user", "settings.tab_user", self._user_page()),
            ("hotkeys", "settings.tab_hotkeys", self._page([self._build_hotkeys_card()])),
            ("substances", "settings.tab_substances",
             self._page([self._build_substances_card()], shared=True)),
        ]
        self._nav_icons: list[tuple[QIcon, QIcon]] = []
        for kind, key, page in specs:
            self._nav_icons.append((_draw_nav_icon(kind), _draw_nav_icon(kind, _NAV_INK_SELECTED)))
            QListWidgetItem(self._nav_icons[-1][0], tr(key), self.nav)
            self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.currentRowChanged.connect(self._sync_nav_icons)
        self.nav.setCurrentRow(0)

        body = QHBoxLayout(); body.setSpacing(18)
        body.addWidget(self.nav)
        body.addWidget(self.stack, 1)

        save = QPushButton(tr("common.save"))
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        save_row = QHBoxLayout(); save_row.addStretch(1); save_row.addWidget(save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 20)
        layout.addLayout(header)
        layout.addLayout(body, 1)
        layout.addLayout(save_row)

    def _sync_nav_icons(self, current: int) -> None:
        """Use the white icon variant on the selected (teal) row, dark on the rest."""
        for i, (dark, light) in enumerate(self._nav_icons):
            self.nav.item(i).setIcon(light if i == current else dark)

    # --- page / card scaffolding -------------------------------------------
    def _page(self, cards: list[QGroupBox], shared: bool = False) -> QScrollArea:
        """A scrollable, left-aligned column of grouped sections (one nav page)."""
        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(4, 4, 14, 4); col.setSpacing(16)
        if shared:
            note = QLabel(tr("settings.shared_note"))
            note.setObjectName("Muted"); note.setWordWrap(True)
            col.addWidget(note)
        for c in cards:
            col.addWidget(c)
        col.addStretch(1)
        content.setMaximumWidth(860)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        return scroll

    def _card(self, title_key: str, intro_key: str | None = None) -> tuple[QGroupBox, QVBoxLayout]:
        """A titled QGroupBox + its vertical layout (shared section scaffolding)."""
        box = QGroupBox(tr(title_key))
        v = QVBoxLayout(box)
        v.setContentsMargins(16, 14, 16, 14); v.setSpacing(10)
        if intro_key:
            intro = QLabel(tr(intro_key)); intro.setObjectName("Muted"); intro.setWordWrap(True)
            v.addWidget(intro)
        return box, v

    def _session_page(self) -> QScrollArea:
        return self._page([self._build_clinical_card(), self._build_session_options_card(),
                           self._build_autoscroll_card(), self._build_accessibility_card(),
                           self._build_advanced_card()])

    # --- session run-option defaults (Session) ------------------------------
    def _build_session_options_card(self) -> QGroupBox:
        cfg = self.context.config
        box, v = self._card("settings.session_options_title", "settings.session_options_hint")
        self.default_random_order = QCheckBox(tr("setup.random_order"))
        self.default_random_order.setChecked(cfg.default_random_order)
        self.default_loop = QCheckBox(tr("setup.loop_cues"))
        self.default_loop.setChecked(cfg.default_loop)
        self.default_start_fullscreen = QCheckBox(tr("setup.start_fullscreen"))
        self.default_start_fullscreen.setChecked(cfg.default_start_fullscreen)
        v.addWidget(self.default_random_order)
        v.addWidget(self.default_loop)
        v.addWidget(self.default_start_fullscreen)
        return box

    def _user_page(self) -> QScrollArea:
        return self._page([self._build_contacts_card(), self._build_language_card(),
                           self._build_branding_card()])

    # --- clinical parameters (Session) --------------------------------------
    def _build_clinical_card(self) -> QGroupBox:
        box, v = self._card("settings.clinical_title")
        form = QFormLayout(); form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.addRow(tr("settings.time_cap_min"), self.time_cap)
        form.addRow(tr("settings.periodic_sec"), self.periodic)
        form.addRow(tr("settings.habituation_threshold"), self.threshold)
        form.addRow(tr("settings.habituation_consecutive"), self.consecutive)
        v.addLayout(form)
        return box

    # --- safety contacts (User) ---------------------------------------------
    def _build_contacts_card(self) -> QGroupBox:
        box, v = self._card("settings.contacts_title")
        form = QFormLayout(); form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.addRow(tr("settings.therapist_phone"), self.therapist)
        form.addRow(tr("settings.crisis_line"), self.crisis)
        form.addRow(tr("settings.emergency"), self.emergency)
        v.addLayout(form)
        return box

    # --- advanced craving prompts (Session) ---------------------------------
    def _build_advanced_card(self) -> QGroupBox:
        cfg = self.context.config
        box, v = self._card("settings.advanced_title", "settings.advanced_hint")
        self.vas_after_coping = QCheckBox(tr("settings.vas_after_coping"))
        self.vas_after_coping.setChecked(cfg.vas_prompt_after_coping)
        self.vas_every_n = QSpinBox(); self.vas_every_n.setRange(0, 20)
        self.vas_every_n.setValue(cfg.vas_prompt_every_n_cues)
        form = QFormLayout(); form.setSpacing(10)
        form.addRow("", self.vas_after_coping)
        form.addRow(tr("settings.vas_every_n_cues"), self.vas_every_n)
        v.addLayout(form)
        return box

    # --- UI language (User) -------------------------------------------------
    def _build_language_card(self) -> QGroupBox:
        box, v = self._card("app.language")
        self.lang_combo = QComboBox()
        for code, name in available_locales():
            self.lang_combo.addItem(name, code)
        idx = self.lang_combo.findData(current_locale())
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        # Live re-render: changing the language rebuilds this screen in the new language.
        self.lang_combo.activated.connect(self._on_language_changed)
        form = QFormLayout(); form.setSpacing(12)
        form.addRow(tr("app.language"), self.lang_combo)
        v.addLayout(form)
        return box

    def _on_language_changed(self, index: int) -> None:
        code = self.lang_combo.itemData(index)
        self.window.change_language(code, redisplay=self.window.show_settings)

    # --- auto-scroll cues (Session) -----------------------------------------
    def _build_autoscroll_card(self) -> QGroupBox:
        cfg = self.context.config
        box, v = self._card("settings.autoscroll_title", "settings.autoscroll_hint")
        self.autoscroll_on_grading = QCheckBox(tr("settings.autoscroll_on_grading"))
        self.autoscroll_on_grading.setChecked(cfg.autoscroll_on_grading)
        self.autoscroll_timed = QSpinBox(); self.autoscroll_timed.setRange(0, 600)
        self.autoscroll_timed.setSuffix(" s")
        self.autoscroll_timed.setValue(cfg.autoscroll_timed_seconds)
        form = QFormLayout(); form.setSpacing(10)
        form.addRow("", self.autoscroll_on_grading)
        form.addRow(tr("settings.autoscroll_timed"), self.autoscroll_timed)
        v.addLayout(form)
        return box

    # --- accessibility (Session) --------------------------------------------
    def _build_accessibility_card(self) -> QGroupBox:
        cfg = self.context.config
        box, v = self._card("settings.accessibility_title", "settings.accessibility_hint")
        self.accessibility_kbmode = QCheckBox(tr("settings.accessibility_kbmode"))
        self.accessibility_kbmode.setChecked(cfg.accessibility_kbmode)
        v.addWidget(self.accessibility_kbmode)
        return box

    # --- hotkey rebinding (Hotkeys) -----------------------------------------
    def _build_hotkeys_card(self) -> QGroupBox:
        box, v = self._card("settings.hotkeys_title", "settings.hotkeys_intro")
        resolved = hotkeys.resolve_bindings(self.context.repos.settings)
        self._hotkey_buttons: dict[str, KeyCaptureButton] = {}

        # Two-column grid keeps the long action list from overflowing the page.
        rows: list[tuple[QLabel, QWidget]] = []
        for act in hotkeys.ACTIONS:
            lbl = QLabel(tr(act.label_key))
            if not act.rebindable:
                w: QWidget = QLabel(f"{resolved[act.id]}  ·  {tr('settings.hotkey_locked')}")
                w.setObjectName("Muted")
            else:
                w = KeyCaptureButton(act.id, resolved[act.id])
                w.captured.connect(self._on_hotkey_captured)
                self._hotkey_buttons[act.id] = w
            rows.append((lbl, w))

        grid = QGridLayout(); grid.setHorizontalSpacing(18); grid.setVerticalSpacing(8)
        half = (len(rows) + 1) // 2
        for i, (lbl, w) in enumerate(rows):
            col = 0 if i < half else 2
            r = i if i < half else i - half
            grid.addWidget(lbl, r, col)
            grid.addWidget(w, r, col + 1)
        grid.setColumnStretch(1, 1); grid.setColumnStretch(3, 1)
        v.addLayout(grid)

        reset = QPushButton(tr("settings.hotkey_reset"))
        reset.clicked.connect(self._reset_hotkeys)
        note = QLabel(tr("settings.hotkeys_apply_note")); note.setObjectName("Muted"); note.setWordWrap(True)
        row = QHBoxLayout(); row.addWidget(reset); row.addStretch(1)
        v.addLayout(row)
        v.addWidget(note)
        return box

    def _on_hotkey_captured(self, action_id: str, keyseq: str) -> None:
        act = next(a for a in hotkeys.ACTIONS if a.id == action_id)
        # ACCESS actions are restricted to the disability keyset.
        if act.scope is hotkeys.Scope.ACCESS and keyseq not in hotkeys.ACCESSIBILITY_KEYSET:
            QMessageBox.warning(self, tr("app.title"), tr("settings.hotkey_not_in_keyset"))
            return
        # Reject a duplicate within the same scope.
        resolved = hotkeys.resolve_bindings(self.context.repos.settings)
        for other in hotkeys.actions_in(act.scope):
            if other.id != action_id and resolved[other.id] == keyseq:
                QMessageBox.warning(self, tr("app.title"), tr("settings.hotkey_conflict"))
                return
        hotkeys.save_binding(self.context.repos.settings, action_id, keyseq)
        self._hotkey_buttons[action_id].set_keyseq(keyseq)
        self.window.reload_global_hotkeys()  # GLOBAL rebinds apply live

    def _reset_hotkeys(self) -> None:
        hotkeys.reset_bindings(self.context.repos.settings)
        defaults = hotkeys.default_bindings()
        for aid, btn in self._hotkey_buttons.items():
            btn.set_keyseq(defaults[aid])
        self.window.reload_global_hotkeys()

    # --- clinic branding for PDF reports (User) -----------------------------
    def _build_branding_card(self) -> QGroupBox:
        s = self.context.repos.settings
        box, v = self._card("settings.branding_title", "settings.branding_intro")
        shared = QLabel(tr("settings.shared_note")); shared.setObjectName("Muted"); shared.setWordWrap(True)
        v.addWidget(shared)

        self.clinic_name = QLineEdit(s.get("clinic_name", "") or "")
        form = QFormLayout(); form.setSpacing(12)
        form.addRow(tr("settings.clinic_name"), self.clinic_name)
        v.addLayout(form)

        self.logo_label = QLabel()
        self._refresh_logo_label()
        pick = QPushButton(tr("settings.logo_pick")); pick.clicked.connect(self._pick_logo)
        clear = QPushButton(tr("settings.logo_clear")); clear.clicked.connect(self._clear_logo)
        row = QHBoxLayout(); row.addWidget(self.logo_label, 1); row.addWidget(pick); row.addWidget(clear)
        v.addLayout(row)
        return box

    def _refresh_logo_label(self) -> None:
        path = self.context.repos.settings.get("clinic_logo_path")
        if path and Path(path).is_file():
            self.logo_label.setText(tr("settings.logo_set", name=Path(path).name))
        else:
            self.logo_label.setText(tr("settings.logo_none"))

    def _pick_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("settings.logo_pick"), "", "Imagen (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        src = Path(path)
        dest = Path(self.context.config.data_dir) / f"clinic_logo{src.suffix.lower()}"
        try:
            # Remove any prior logo with a different extension, then copy the new one.
            for old in Path(self.context.config.data_dir).glob("clinic_logo.*"):
                if old != dest:
                    old.unlink()
            if src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
        except OSError as exc:
            QMessageBox.warning(self, tr("app.title"), str(exc))
            return
        self.context.repos.settings.set("clinic_logo_path", str(dest))
        self._refresh_logo_label()

    def _clear_logo(self) -> None:
        self.context.repos.settings.set("clinic_logo_path", "")
        self._refresh_logo_label()

    # --- custom substances (Substances) -------------------------------------
    def _build_substances_card(self) -> QGroupBox:
        box, v = self._card("settings.substances_title", "settings.substances_intro")
        self.subs_list = QListWidget()
        self.subs_list.setMaximumHeight(200)

        add_btn = QPushButton(tr("settings.substance_add")); add_btn.clicked.connect(self._add_substance)
        del_btn = QPushButton(tr("settings.substance_remove")); del_btn.setObjectName("Danger")
        del_btn.clicked.connect(self._remove_substance)
        btns = QHBoxLayout(); btns.addWidget(add_btn); btns.addStretch(1); btns.addWidget(del_btn)

        v.addWidget(self.subs_list); v.addLayout(btns)
        self._refresh_substances()
        return box

    def _refresh_substances(self) -> None:
        self.subs_list.clear()
        settings = self.context.repos.settings
        for key in subs.BUILTIN_KEYS:
            item = QListWidgetItem(f"{subs.display_name(settings, key)}  ·  {tr('settings.substance_builtin')}")
            item.setData(Qt.ItemDataRole.UserRole, None)  # locked
            self.subs_list.addItem(item)
        for key, label in subs.custom_substances(settings):
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.subs_list.addItem(item)

    def _add_substance(self) -> None:
        label, ok = QInputDialog.getText(self, tr("settings.substance_add"), tr("settings.substance_prompt"))
        if not (ok and label.strip()):
            return
        key = subs.add_custom(self.context.repos.settings, label)
        if key is None:
            QMessageBox.warning(self, tr("app.title"), tr("settings.substance_dupe"))
            return
        (self.context.config.media_root / key).mkdir(parents=True, exist_ok=True)
        self._refresh_substances()

    def _remove_substance(self) -> None:
        item = self.subs_list.currentItem()
        key = item.data(Qt.ItemDataRole.UserRole) if item else None
        if key is None:
            QMessageBox.information(self, tr("app.title"), tr("settings.substance_builtin_locked"))
            return
        confirm = QMessageBox.question(self, tr("app.title"),
                                       tr("settings.substance_remove_confirm", name=item.text()))
        if confirm == QMessageBox.StandardButton.Yes:
            subs.hide_custom(self.context.repos.settings, key)
            self._refresh_substances()

    def _save(self) -> None:
        cfg = self.context.config
        self.context.crisis.save(CrisisInfo(
            therapist_phone=self.therapist.text().strip(),
            crisis_line=self.crisis.text().strip(),
            emergency_number=self.emergency.text().strip(),
        ))
        s = self.context.repos.settings
        cfg.session_time_cap_seconds = self.time_cap.value() * 60
        cfg.periodic_vas_seconds = self.periodic.value()
        cfg.habituation_threshold = self.threshold.value()
        cfg.habituation_consecutive = self.consecutive.value()
        s.set("time_cap_seconds", str(cfg.session_time_cap_seconds))
        s.set("periodic_vas_seconds", str(cfg.periodic_vas_seconds))
        s.set("habituation_threshold", str(cfg.habituation_threshold))
        s.set("habituation_consecutive", str(cfg.habituation_consecutive))
        if hasattr(self, "autoscroll_on_grading"):
            cfg.autoscroll_on_grading = self.autoscroll_on_grading.isChecked()
            cfg.autoscroll_timed_seconds = self.autoscroll_timed.value()
            s.set("autoscroll_on_grading", "1" if cfg.autoscroll_on_grading else "0")
            s.set("autoscroll_timed_seconds", str(cfg.autoscroll_timed_seconds))
        if hasattr(self, "accessibility_kbmode"):
            cfg.accessibility_kbmode = self.accessibility_kbmode.isChecked()
            s.set("accessibility_kbmode", "1" if cfg.accessibility_kbmode else "0")
        if hasattr(self, "vas_after_coping"):
            cfg.vas_prompt_after_coping = self.vas_after_coping.isChecked()
            cfg.vas_prompt_every_n_cues = self.vas_every_n.value()
            s.set("vas_prompt_after_coping", "1" if cfg.vas_prompt_after_coping else "0")
            s.set("vas_prompt_every_n_cues", str(cfg.vas_prompt_every_n_cues))
        if hasattr(self, "default_random_order"):
            cfg.default_random_order = self.default_random_order.isChecked()
            cfg.default_loop = self.default_loop.isChecked()
            cfg.default_start_fullscreen = self.default_start_fullscreen.isChecked()
            s.set("default_random_order", "1" if cfg.default_random_order else "0")
            s.set("default_loop", "1" if cfg.default_loop else "0")
            s.set("default_start_fullscreen", "1" if cfg.default_start_fullscreen else "0")
        if hasattr(self, "clinic_name"):
            s.set("clinic_name", self.clinic_name.text().strip())
        QMessageBox.information(self, tr("app.title"), tr("settings.saved"))
