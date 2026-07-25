"""Clinic settings: safety contacts and clinical parameters (persisted to app_setting)."""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
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
    QVBoxLayout,
    QWidget,
)

from ...services import substances as subs
from ...services.crisis import CrisisInfo
from ...services.i18n import available_locales, current_locale, tr
from .. import hotkeys
from ..context import AppContext
from ..widgets.key_capture_button import KeyCaptureButton

_CARD_STYLE = (
    "QLabel { font-size: 16px; }"
    "QLineEdit, QSpinBox { font-size: 17px; min-height: 30px; padding: 6px 9px; }"
    "QSpinBox::up-button, QSpinBox::down-button { width: 22px; }"
    "QListWidget { font-size: 16px; }"
    "QPushButton { font-size: 15px; padding: 8px 14px; }"
    "QPushButton#Primary { font-size: 16px; padding: 10px 18px; }"
)


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
        header = QHBoxLayout()
        header.addWidget(back); header.addSpacing(10); header.addWidget(title); header.addStretch(1)

        self.therapist = QLineEdit(info.therapist_phone)
        self.crisis = QLineEdit(info.crisis_line)
        self.emergency = QLineEdit(info.emergency_number)

        self.time_cap = QSpinBox(); self.time_cap.setRange(1, 120)
        self.time_cap.setValue(cfg.session_time_cap_seconds // 60)
        self.periodic = QSpinBox(); self.periodic.setRange(5, 300)
        self.periodic.setValue(cfg.periodic_vas_seconds)
        self.threshold = QSpinBox(); self.threshold.setRange(0, cfg.vas_max)
        self.threshold.setValue(cfg.habituation_threshold)
        self.consecutive = QSpinBox(); self.consecutive.setRange(1, 10)
        self.consecutive.setValue(cfg.habituation_consecutive)

        card = QFrame(); card.setObjectName("Card"); card.setMaximumWidth(760)
        # Comfortably-readable inputs (the defaults were too cramped for clinical use).
        card.setStyleSheet(_CARD_STYLE)
        form = QFormLayout(card)
        form.setContentsMargins(28, 24, 28, 24)
        form.setSpacing(16)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.addRow(tr("settings.therapist_phone"), self.therapist)
        form.addRow(tr("settings.crisis_line"), self.crisis)
        form.addRow(tr("settings.emergency"), self.emergency)
        form.addRow(tr("settings.time_cap_min"), self.time_cap)
        form.addRow(tr("settings.periodic_sec"), self.periodic)
        form.addRow(tr("settings.habituation_threshold"), self.threshold)
        form.addRow(tr("settings.habituation_consecutive"), self.consecutive)

        save = QPushButton(tr("common.save"))
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        form.addRow(save)

        language_card = self._build_language_card()
        autoscroll_card = self._build_autoscroll_card()
        accessibility_card = self._build_accessibility_card()
        hotkeys_card = self._build_hotkeys_card()
        substances_card = self._build_substances_card()
        branding_card = self._build_branding_card()

        # Scroll area so the growing settings list stays usable on small screens.
        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(20)
        for c in (card, language_card, autoscroll_card, accessibility_card,
                  hotkeys_card, branding_card, substances_card):
            row = QHBoxLayout(); row.addStretch(1); row.addWidget(c); row.addStretch(1)
            col.addLayout(row)
        col.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.addLayout(header)
        layout.addWidget(scroll, 1)

    # --- UI language --------------------------------------------------------
    def _build_language_card(self) -> QFrame:
        card = QFrame(); card.setObjectName("Card"); card.setMaximumWidth(760)
        card.setStyleSheet(_CARD_STYLE)
        v = QVBoxLayout(card)
        v.setContentsMargins(28, 24, 28, 24); v.setSpacing(12)

        title = QLabel(tr("app.language")); title.setObjectName("H2")
        v.addWidget(title)

        self.lang_combo = QComboBox()
        for code, name in available_locales():
            self.lang_combo.addItem(name, code)
        current = current_locale()
        idx = self.lang_combo.findData(current)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        # Live re-render: changing the language rebuilds this screen in the new language.
        self.lang_combo.activated.connect(self._on_language_changed)

        form = QFormLayout(); form.setSpacing(12)
        form.addRow(tr("app.language"), self.lang_combo)
        v.addLayout(form)
        return card

    def _on_language_changed(self, index: int) -> None:
        code = self.lang_combo.itemData(index)
        self.window.change_language(code, redisplay=self.window.show_settings)

    # --- auto-scroll cues ---------------------------------------------------
    def _build_autoscroll_card(self) -> QFrame:
        cfg = self.context.config
        card = QFrame(); card.setObjectName("Card"); card.setMaximumWidth(760)
        card.setStyleSheet(_CARD_STYLE)
        v = QVBoxLayout(card)
        v.setContentsMargins(28, 24, 28, 24); v.setSpacing(12)

        title = QLabel(tr("settings.autoscroll_title")); title.setObjectName("H2")
        intro = QLabel(tr("settings.autoscroll_hint")); intro.setObjectName("Muted"); intro.setWordWrap(True)
        v.addWidget(title); v.addWidget(intro)

        self.autoscroll_on_grading = QCheckBox(tr("settings.autoscroll_on_grading"))
        self.autoscroll_on_grading.setChecked(cfg.autoscroll_on_grading)
        self.autoscroll_timed = QSpinBox(); self.autoscroll_timed.setRange(0, 600)
        self.autoscroll_timed.setValue(cfg.autoscroll_timed_seconds)

        form = QFormLayout(); form.setSpacing(12)
        form.addRow("", self.autoscroll_on_grading)
        form.addRow(tr("settings.autoscroll_timed"), self.autoscroll_timed)
        v.addLayout(form)
        return card

    # --- accessibility (keyboard-only exposure mode) ------------------------
    def _build_accessibility_card(self) -> QFrame:
        cfg = self.context.config
        card = QFrame(); card.setObjectName("Card"); card.setMaximumWidth(760)
        card.setStyleSheet(_CARD_STYLE)
        v = QVBoxLayout(card)
        v.setContentsMargins(28, 24, 28, 24); v.setSpacing(12)

        title = QLabel(tr("settings.accessibility_title")); title.setObjectName("H2")
        intro = QLabel(tr("settings.accessibility_hint")); intro.setObjectName("Muted"); intro.setWordWrap(True)
        self.accessibility_kbmode = QCheckBox(tr("settings.accessibility_kbmode"))
        self.accessibility_kbmode.setChecked(cfg.accessibility_kbmode)
        v.addWidget(title); v.addWidget(intro); v.addWidget(self.accessibility_kbmode)
        return card

    # --- hotkey rebinding ---------------------------------------------------
    def _build_hotkeys_card(self) -> QFrame:
        card = QFrame(); card.setObjectName("Card"); card.setMaximumWidth(760)
        card.setStyleSheet(_CARD_STYLE)
        v = QVBoxLayout(card)
        v.setContentsMargins(28, 24, 28, 24); v.setSpacing(12)

        title = QLabel(tr("settings.hotkeys_title")); title.setObjectName("H2")
        intro = QLabel(tr("settings.hotkeys_intro")); intro.setObjectName("Muted"); intro.setWordWrap(True)
        note = QLabel(tr("settings.hotkeys_apply_note")); note.setObjectName("Muted"); note.setWordWrap(True)
        v.addWidget(title); v.addWidget(intro)

        resolved = hotkeys.resolve_bindings(self.context.repos.settings)
        self._hotkey_buttons: dict[str, KeyCaptureButton] = {}
        form = QFormLayout(); form.setSpacing(10)
        for act in hotkeys.ACTIONS:
            if not act.rebindable:
                locked = QLabel(f"{resolved[act.id]}  ·  {tr('settings.hotkey_locked')}")
                locked.setObjectName("Muted")
                form.addRow(tr(act.label_key), locked)
                continue
            btn = KeyCaptureButton(act.id, resolved[act.id])
            btn.captured.connect(self._on_hotkey_captured)
            self._hotkey_buttons[act.id] = btn
            form.addRow(tr(act.label_key), btn)
        v.addLayout(form)

        reset = QPushButton(tr("settings.hotkey_reset"))
        reset.clicked.connect(self._reset_hotkeys)
        v.addWidget(reset)
        v.addWidget(note)
        return card

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

    # --- clinic branding for PDF reports ------------------------------------
    def _build_branding_card(self) -> QFrame:
        s = self.context.repos.settings
        card = QFrame(); card.setObjectName("Card"); card.setMaximumWidth(760)
        card.setStyleSheet(_CARD_STYLE)
        v = QVBoxLayout(card)
        v.setContentsMargins(28, 24, 28, 24); v.setSpacing(12)

        title = QLabel(tr("settings.branding_title")); title.setObjectName("H2")
        intro = QLabel(tr("settings.branding_intro")); intro.setObjectName("Muted"); intro.setWordWrap(True)
        v.addWidget(title); v.addWidget(intro)

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
        return card

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

    # --- custom substances --------------------------------------------------
    def _build_substances_card(self) -> QFrame:
        card = QFrame(); card.setObjectName("Card"); card.setMaximumWidth(760)
        card.setStyleSheet(_CARD_STYLE)
        v = QVBoxLayout(card)
        v.setContentsMargins(28, 24, 28, 24); v.setSpacing(12)

        title = QLabel(tr("settings.substances_title")); title.setObjectName("H2")
        intro = QLabel(tr("settings.substances_intro")); intro.setObjectName("Muted"); intro.setWordWrap(True)
        self.subs_list = QListWidget()
        self.subs_list.setMaximumHeight(180)

        add_btn = QPushButton(tr("settings.substance_add")); add_btn.clicked.connect(self._add_substance)
        del_btn = QPushButton(tr("settings.substance_remove")); del_btn.setObjectName("Danger")
        del_btn.clicked.connect(self._remove_substance)
        btns = QHBoxLayout(); btns.addWidget(add_btn); btns.addStretch(1); btns.addWidget(del_btn)

        v.addWidget(title); v.addWidget(intro); v.addWidget(self.subs_list); v.addLayout(btns)
        self._refresh_substances()
        return card

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
        if hasattr(self, "clinic_name"):
            s.set("clinic_name", self.clinic_name.text().strip())
        QMessageBox.information(self, tr("app.title"), tr("settings.saved"))
