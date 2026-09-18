"""Admin Center — key-gated hub for admin quality-of-life tools.

Phase 1 (0.6.0): Backup & restore (DB + media), Storage info, and the Admin audit log. Reuses the
Settings master-detail look (icon nav + stacked QGroupBox pages). Reached via a key-gated **Admin**
button on the dashboard; the key check happens in ``ui/widgets/admin_gate.py`` before this screen
is shown.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ... import __version__
from ...domain import reports
from ...domain.uscs import USCS_STEPS
from ...services import backup, cue_ranking, export, patient_admin, patient_bundle
from ...services.i18n import tr
from ..context import AppContext
from ..responsive import adaptive_margins, adaptive_nav_width, screen_size
from .settings_screen import _NAV_INK_SELECTED, _draw_nav_icon


def _fmt_size(num_bytes: int) -> str:
    mb = num_bytes / (1024 * 1024)
    return f"{mb:.1f} MB" if mb >= 0.1 else f"{num_bytes / 1024:.0f} KB"


class AdminCenterScreen(QWidget):
    def __init__(self, window, context: AppContext) -> None:
        super().__init__()
        self.window = window
        self.context = context
        self._backed_up = False   # tracks whether a backup was made this session

        back = QPushButton(tr("common.back"))
        back.clicked.connect(window.show_dashboard)
        title = QLabel(tr("admin.center_title")); title.setObjectName("H1")
        help_btn = QPushButton(tr("common.help"))
        help_btn.clicked.connect(lambda: self.window.show_help("admin_center"))
        header = QHBoxLayout()
        header.addWidget(back); header.addSpacing(10); header.addWidget(title)
        header.addStretch(1); header.addWidget(help_btn)

        self.nav = QListWidget(); self.nav.setObjectName("SettingsNav")
        self.nav.setFixedWidth(adaptive_nav_width()); self.nav.setIconSize(QSize(24, 24))
        self.nav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.stack = QStackedWidget()
        specs = [
            ("backup", "admin.tab_backup", self._backup_page()),
            ("data", "admin.tab_data", self._data_page()),
            ("clinicians", "admin.tab_clinicians", self._clinicians_page()),
            ("clinic", "admin.tab_clinic", self._clinic_page()),
            ("reports", "admin.tab_reports", self._reports_page()),
            ("storage", "admin.tab_storage", self._storage_page()),
            ("audit", "admin.tab_audit", self._audit_page()),
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
        body.addWidget(self.nav); body.addWidget(self.stack, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*adaptive_margins())
        layout.addLayout(header)
        layout.addLayout(body, 1)

    def _sync_nav_icons(self, current: int) -> None:
        for i, (dark, light) in enumerate(self._nav_icons):
            self.nav.item(i).setIcon(light if i == current else dark)

    # --- scaffolding (mirrors SettingsScreen) -------------------------------
    def _page(self, cards: list[QGroupBox]) -> QScrollArea:
        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(4, 4, 14, 4); col.setSpacing(16)
        for c in cards:
            col.addWidget(c)
        col.addStretch(1)
        content.setMaximumWidth(min(860, screen_size()[0] - adaptive_nav_width() - 80))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        return scroll

    def _card(self, title_key: str, intro_key: str | None = None) -> tuple[QGroupBox, QVBoxLayout]:
        box = QGroupBox(tr(title_key))
        v = QVBoxLayout(box)
        v.setContentsMargins(16, 14, 16, 14); v.setSpacing(10)
        if intro_key:
            intro = QLabel(tr(intro_key)); intro.setObjectName("Muted"); intro.setWordWrap(True)
            v.addWidget(intro)
        return box, v

    def _actor(self) -> str:
        c = self.context.clinician
        return c.username if c else "admin"

    # --- Backup page --------------------------------------------------------
    def _backup_page(self) -> QScrollArea:
        box, v = self._card("admin.tab_backup", "admin.backup_intro")
        create = QPushButton(tr("admin.backup_create")); create.setObjectName("Primary")
        create.clicked.connect(self._create_backup)
        restore = QPushButton(tr("admin.backup_restore"))
        restore.clicked.connect(self._restore_backup)
        row = QHBoxLayout(); row.addWidget(create); row.addWidget(restore); row.addStretch(1)
        v.addLayout(row)
        return self._page([box])

    def _create_backup(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        cfg = self.context.config
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default = str(Path(cfg.data_dir) / f"cetus_backup_{stamp}.zip")
        path, _ = QFileDialog.getSaveFileName(self, tr("admin.backup_create"), default, "Zip (*.zip)")
        if not path:
            return
        repos = self.context.repos
        counts = {"patients": repos.patients.count(), "sessions": repos.sessions.count(),
                  "clinicians": repos.clinicians.count()}
        try:
            manifest = backup.create_backup(
                cfg.db_path, cfg.media_root, path, __version__,
                datetime.now(UTC).isoformat(), counts)
        except Exception as exc:  # noqa: BLE001 - surface any IO/zip failure honestly
            QMessageBox.warning(self, tr("admin.center_title"), tr("admin.backup_failed", err=str(exc)))
            return
        repos.audit.log("backup_create", Path(path).name, self._actor())
        self._backed_up = True
        QMessageBox.information(self, tr("admin.center_title"),
                                tr("admin.backup_done", n=manifest["counts"].get("patients", 0),
                                   media=manifest.get("media_file_count", 0)))

    def _restore_backup(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        cfg = self.context.config
        path, _ = QFileDialog.getOpenFileName(
            self, tr("admin.backup_restore"), str(cfg.data_dir), "Zip (*.zip)")
        if not path:
            return
        manifest = backup.read_manifest(path)
        if manifest is None:
            QMessageBox.warning(self, tr("admin.center_title"), tr("admin.restore_invalid"))
            return
        confirm = QMessageBox.question(
            self, tr("admin.center_title"),
            tr("admin.restore_confirm", date=manifest.get("created_at", "?"),
               n=manifest.get("counts", {}).get("patients", "?")))
        if confirm != QMessageBox.StandardButton.Yes:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pre = Path(cfg.data_dir) / f"cetus_pre_restore_{stamp}.zip"
        # Log before closing the DB (the entry rides along in the pre-restore safety zip).
        self.context.repos.audit.log("backup_restore", Path(path).name, self._actor())
        try:
            self.context.db.close()
            backup.restore_backup(cfg.db_path, cfg.media_root, path, pre,
                                  __version__, datetime.now(UTC).isoformat())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, tr("admin.center_title"), tr("admin.backup_failed", err=str(exc)))
            return
        QMessageBox.information(self, tr("admin.center_title"), tr("admin.restore_done"))
        QApplication.instance().quit()   # relaunch on the restored data

    # --- Data page (per-patient handling) -----------------------------------
    def _data_page(self) -> QScrollArea:
        box, v = self._card("admin.tab_data", "admin.data_intro")
        self.patient_combo = QComboBox()
        self._refresh_patients()
        v.addWidget(self.patient_combo)

        export_btn = QPushButton(tr("admin.data_export")); export_btn.setObjectName("Primary")
        export_btn.clicked.connect(self._export_bundle)
        anon_btn = QPushButton(tr("admin.data_anonymize"))
        anon_btn.clicked.connect(self._anonymize_patient)
        del_btn = QPushButton(tr("admin.data_delete")); del_btn.setObjectName("Danger")
        del_btn.clicked.connect(self._hard_delete_patient)
        row = QHBoxLayout()
        row.addWidget(export_btn); row.addWidget(anon_btn); row.addStretch(1); row.addWidget(del_btn)
        v.addLayout(row)
        return self._page([box])

    def _refresh_patients(self) -> None:
        self.patient_combo.clear()
        for p in self.context.repos.patients.list_all():
            label = p.code + (f"  ·  {tr('admin.data_archived')}" if p.archived else "")
            self.patient_combo.addItem(label, p.id)

    def _selected_patient(self):
        pid = self.patient_combo.currentData()
        return self.context.repos.patients.get(pid) if pid is not None else None

    @staticmethod
    def _skill_labels() -> dict:
        return {s.skill.value: tr(s.title_key) for s in USCS_STEPS}

    def _confirm_code(self, patient, prompt: str) -> bool:
        """Destructive-action gate: the operator must type the patient's code exactly."""
        text, ok = QInputDialog.getText(self, tr("admin.center_title"), prompt,
                                        QLineEdit.EchoMode.Normal)
        return bool(ok and text.strip() == patient.code)

    def _export_bundle(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        p = self._selected_patient()
        if p is None:
            return
        repos = self.context.repos
        sessions = repos.sessions.list_for_patient(p.id)
        per = {s.id: (repos.ratings.list_for_session(s.id),
                      repos.coping.list_for_session(s.id),
                      repos.intensity.list_for_session(s.id)) for s in sessions}
        coping_pairs = [(s, per[s.id][1]) for s in sessions]
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default = str(Path(self.context.config.data_dir) / f"cetus_{p.code}_bundle_{stamp}.zip")
        path, _ = QFileDialog.getSaveFileName(self, tr("admin.data_export"), default, "Zip (*.zip)")
        if not path:
            return
        try:
            res = patient_bundle.create_patient_bundle(
                path, p.code, sessions, per, coping_pairs, self._skill_labels())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("admin.center_title"), tr("admin.backup_failed", err=str(exc)))
            return
        repos.audit.log("patient_export", p.code, self._actor())
        QMessageBox.information(self, tr("admin.center_title"),
                                tr("admin.data_export_done", files=res["files"]))

    def _anonymize_patient(self) -> None:
        p = self._selected_patient()
        if p is None:
            return
        if not self._confirm_code(p, tr("admin.data_anonymize_confirm", code=p.code)):
            return
        self.context.repos.patients.anonymize(p.id)
        self.context.repos.audit.log("patient_anonymize", p.code, self._actor())
        self._refresh_patients()
        QMessageBox.information(self, tr("admin.center_title"),
                                tr("admin.data_anonymize_done", code=p.code))

    def _hard_delete_patient(self) -> None:
        p = self._selected_patient()
        if p is None:
            return
        if not self._backed_up and QMessageBox.question(
                self, tr("admin.center_title"), tr("admin.data_no_backup_warn")
        ) != QMessageBox.StandardButton.Yes:
            return
        if not self._confirm_code(p, tr("admin.data_delete_confirm", code=p.code)):
            return
        res = patient_admin.hard_delete_patient(
            self.context.repos, self.context.config.media_root, p.id)
        self.context.repos.audit.log(
            "patient_delete", f"{p.code} (media -{res['media_removed']})", self._actor())
        self._refresh_patients()
        QMessageBox.information(self, tr("admin.center_title"),
                                tr("admin.data_delete_done", code=p.code))

    # --- Clinicians page ----------------------------------------------------
    def _clinicians_page(self) -> QScrollArea:
        box, v = self._card("admin.tab_clinicians", "admin.clinicians_intro")
        self.clinician_list = QListWidget(); self.clinician_list.setMinimumHeight(200)
        self._refresh_clinicians()
        v.addWidget(self.clinician_list)
        rename = QPushButton(tr("admin.clinician_rename")); rename.clicked.connect(self._rename_clinician)
        toggle = QPushButton(tr("admin.clinician_toggle")); toggle.clicked.connect(self._toggle_clinician)
        transfer = QPushButton(tr("admin.clinician_transfer")); transfer.clicked.connect(self._transfer_patients)
        delete = QPushButton(tr("admin.clinician_delete")); delete.setObjectName("Danger")
        delete.clicked.connect(self._delete_clinician)
        row = QHBoxLayout()
        row.addWidget(rename); row.addWidget(toggle); row.addWidget(transfer)
        row.addStretch(1); row.addWidget(delete)
        v.addLayout(row)
        return self._page([box])

    def _refresh_clinicians(self) -> None:
        self.clinician_list.clear()
        for c in self.context.repos.clinicians.list_all():
            tag = f"  ·  {tr('admin.clinician_disabled')}" if c.disabled else ""
            item = QListWidgetItem(f"{c.username}  —  {c.display_name}{tag}")
            item.setData(Qt.ItemDataRole.UserRole, c.id)
            self.clinician_list.addItem(item)

    def _selected_clinician(self):
        item = self.clinician_list.currentItem()
        cid = item.data(Qt.ItemDataRole.UserRole) if item else None
        if cid is None:
            return None
        return next((c for c in self.context.repos.clinicians.list_all() if c.id == cid), None)

    def _is_self(self, clinician) -> bool:
        return bool(self.context.clinician and clinician.id == self.context.clinician.id)

    def _rename_clinician(self) -> None:
        c = self._selected_clinician()
        if c is None:
            return
        name, ok = QInputDialog.getText(self, tr("admin.clinician_rename"),
                                        tr("admin.clinician_new_name"), QLineEdit.EchoMode.Normal,
                                        c.display_name)
        if ok and name.strip():
            self.context.repos.clinicians.set_display_name(c.id, name.strip())
            self.context.repos.audit.log("clinician_rename", c.username, self._actor())
            self._refresh_clinicians()

    def _toggle_clinician(self) -> None:
        c = self._selected_clinician()
        if c is None:
            return
        if self._is_self(c) and not c.disabled:
            QMessageBox.information(self, tr("admin.center_title"), tr("admin.clinician_not_self"))
            return
        self.context.repos.clinicians.set_disabled(c.id, not c.disabled)
        self.context.repos.audit.log(
            "clinician_enable" if c.disabled else "clinician_disable", c.username, self._actor())
        self._refresh_clinicians()

    def _transfer_patients(self) -> None:
        c = self._selected_clinician()
        if c is None:
            return
        others = [o for o in self.context.repos.clinicians.list_all() if o.id != c.id]
        if not others:
            QMessageBox.information(self, tr("admin.center_title"), tr("admin.clinician_no_target"))
            return
        n = self.context.repos.patients.count_for_owner(c.id)
        labels = [f"{o.username} — {o.display_name}" for o in others]
        choice, ok = QInputDialog.getItem(
            self, tr("admin.clinician_transfer"),
            tr("admin.clinician_transfer_prompt", n=n, who=c.display_name), labels, 0, False)
        if not ok:
            return
        target = others[labels.index(choice)]
        moved = self.context.repos.patients.reassign_owner(c.id, target.id)
        self.context.repos.audit.log(
            "patients_transfer", f"{c.username} -> {target.username} ({moved})", self._actor())
        QMessageBox.information(self, tr("admin.center_title"),
                                tr("admin.clinician_transfer_done", n=moved, who=target.display_name))

    def _delete_clinician(self) -> None:
        c = self._selected_clinician()
        if c is None:
            return
        if self._is_self(c):
            QMessageBox.information(self, tr("admin.center_title"), tr("admin.clinician_not_self"))
            return
        pats, sess = self.context.repos.clinicians.owns_counts(c.id)
        if pats or sess:
            QMessageBox.information(self, tr("admin.center_title"),
                                    tr("admin.clinician_owns", pats=pats, sess=sess))
            return
        if QMessageBox.question(self, tr("admin.center_title"),
                                tr("admin.clinician_delete_confirm", who=c.username)
                                ) != QMessageBox.StandardButton.Yes:
            return
        self.context.repos.clinicians.delete(c.id)
        self.context.repos.audit.log("clinician_delete", c.username, self._actor())
        self._refresh_clinicians()

    # --- Clinic page --------------------------------------------------------
    def _clinic_page(self) -> QScrollArea:
        box, v = self._card("admin.tab_clinic", "admin.clinic_intro")
        s = self.context.repos.settings
        from PySide6.QtWidgets import QFormLayout
        self.clinic_name = QLineEdit(s.get("clinic_name", "") or "")
        self.clinic_address = QLineEdit(s.get("clinic_address", "") or "")
        self.clinic_email = QLineEdit(s.get("clinic_email", "") or "")
        self.clinic_phone = QLineEdit(s.get("clinic_phone", "") or "")
        form = QFormLayout(); form.setSpacing(12)
        form.addRow(tr("settings.clinic_name"), self.clinic_name)
        form.addRow(tr("admin.clinic_address"), self.clinic_address)
        form.addRow(tr("admin.clinic_email"), self.clinic_email)
        form.addRow(tr("admin.clinic_phone"), self.clinic_phone)
        v.addLayout(form)
        save = QPushButton(tr("common.save")); save.setObjectName("Primary")
        save.clicked.connect(self._save_clinic)
        v.addWidget(save)
        return self._page([box])

    def _save_clinic(self) -> None:
        s = self.context.repos.settings
        s.set("clinic_name", self.clinic_name.text().strip())
        s.set("clinic_address", self.clinic_address.text().strip())
        s.set("clinic_email", self.clinic_email.text().strip())
        s.set("clinic_phone", self.clinic_phone.text().strip())
        self.context.repos.audit.log("clinic_update", "", self._actor())
        QMessageBox.information(self, tr("admin.center_title"), tr("settings.saved"))

    # --- Reports page (cohort / per-clinician) ------------------------------
    def _reports_page(self) -> QScrollArea:
        box, v = self._card("admin.tab_reports", "admin.reports_intro")
        self.report_clinician = QComboBox()
        self.report_clinician.addItem(tr("admin.reports_all"), None)
        for c in self.context.repos.clinicians.list_all():
            self.report_clinician.addItem(f"{c.username} — {c.display_name}", c.id)
        v.addWidget(QLabel(tr("admin.reports_filter")))
        v.addWidget(self.report_clinician)

        cohort_csv = QPushButton(tr("admin.reports_cohort_csv")); cohort_csv.setObjectName("Primary")
        cohort_csv.clicked.connect(self._export_cohort_csv)
        cohort_pdf = QPushButton(tr("admin.reports_cohort_pdf"))
        cohort_pdf.clicked.connect(self._export_cohort_pdf)
        activity = QPushButton(tr("admin.reports_activity_csv"))
        activity.clicked.connect(self._export_clinician_activity)
        row = QHBoxLayout()
        row.addWidget(cohort_csv); row.addWidget(cohort_pdf); row.addStretch(1); row.addWidget(activity)
        v.addLayout(row)
        population = QPushButton(tr("admin.reports_population_csv"))
        population.clicked.connect(self._export_population)
        cue_db = QPushButton(tr("admin.reports_cue_db_csv"))
        cue_db.clicked.connect(self._export_cue_db)
        prow = QHBoxLayout(); prow.addWidget(population); prow.addStretch(1); prow.addWidget(cue_db)
        v.addLayout(prow)
        return self._page([box])

    def _export_cue_db(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        rows = cue_ranking.all_cue_order_rows(self.context.repos)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default = str(Path(self.context.config.data_dir) / f"cetus_cue_order_db_{stamp}.csv")
        path, _ = QFileDialog.getSaveFileName(
            self, tr("admin.reports_cue_db_csv"), default, "CSV (*.csv)")
        if not path:
            return
        export.export_cue_order(Path(path), rows)
        self.context.repos.audit.log("cue_order_db_export", f"{len(rows)} rows", self._actor())
        QMessageBox.information(self, tr("admin.center_title"), tr("admin.reports_done", n=len(rows)))

    def _export_population(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        rows = cue_ranking.population_reactivity(self.context.repos)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default = str(Path(self.context.config.data_dir) / f"cetus_population_reactivity_{stamp}.csv")
        path, _ = QFileDialog.getSaveFileName(
            self, tr("admin.reports_population_csv"), default, "CSV (*.csv)")
        if not path:
            return
        export.export_population_reactivity(Path(path), rows)
        self.context.repos.audit.log("population_reactivity_export", f"{len(rows)} groups", self._actor())
        QMessageBox.information(self, tr("admin.center_title"), tr("admin.reports_done", n=len(rows)))

    def _cohort_items(self):
        """(scope_label, [(code, substance, sessions), ...]) for the current filter."""
        repos = self.context.repos
        cid = self.report_clinician.currentData()
        if cid is None:
            patients = repos.patients.list_all()
            scope = tr("admin.reports_all")
        else:
            patients = repos.patients.list_for_clinician(cid)
            scope = self.report_clinician.currentText()
        items = [(p.code, p.primary_substance, repos.sessions.list_for_patient(p.id))
                 for p in patients]
        return scope, items

    def _export_cohort_csv(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        _scope, items = self._cohort_items()
        rows = reports.cohort_summary(items)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default = str(Path(self.context.config.data_dir) / f"cetus_cohort_{stamp}.csv")
        path, _ = QFileDialog.getSaveFileName(self, tr("admin.reports_cohort_csv"), default, "CSV (*.csv)")
        if not path:
            return
        export.export_cohort_summary(Path(path), rows)
        self.context.repos.audit.log("cohort_export_csv", f"{len(rows)} patients", self._actor())
        QMessageBox.information(self, tr("admin.center_title"),
                                tr("admin.reports_done", n=len(rows)))

    def _export_clinician_activity(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        repos = self.context.repos
        rows = [{"clinician": c.username,
                 "patients": repos.patients.count_for_owner(c.id),
                 "sessions": len(repos.sessions.list_for_clinician(c.id))}
                for c in repos.clinicians.list_all()]
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default = str(Path(self.context.config.data_dir) / f"cetus_activity_{stamp}.csv")
        path, _ = QFileDialog.getSaveFileName(self, tr("admin.reports_activity_csv"), default, "CSV (*.csv)")
        if not path:
            return
        export.export_clinician_activity(Path(path), rows)
        repos.audit.log("clinician_activity_export", f"{len(rows)} clinicians", self._actor())
        QMessageBox.information(self, tr("admin.center_title"),
                                tr("admin.reports_done", n=len(rows)))

    def _export_cohort_pdf(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        scope, items = self._cohort_items()
        rows = reports.cohort_summary(items)
        totals = reports.cohort_totals(rows)
        end_reasons = reports.end_reason_counts([s for _c, _s, ss in items for s in ss])
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default = str(Path(self.context.config.data_dir) / f"cetus_cohort_{stamp}.pdf")
        path, _ = QFileDialog.getSaveFileName(self, tr("admin.reports_cohort_pdf"), default, "PDF (*.pdf)")
        if not path:
            return
        self._write_cohort_pdf(path, scope, rows, totals, end_reasons)
        self.context.repos.audit.log("cohort_export_pdf", f"{len(rows)} patients", self._actor())
        QMessageBox.information(self, tr("admin.center_title"),
                                tr("admin.reports_done", n=len(rows)))

    def _write_cohort_pdf(self, path, scope, rows, totals, end_reasons) -> None:
        from PySide6.QtCore import QMarginsF, QSizeF
        from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument
        writer = QPdfWriter(str(path))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(QPageLayout.Orientation.Landscape)
        writer.setResolution(200)
        writer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)
        paint = writer.pageLayout().paintRectPixels(writer.resolution())
        doc = QTextDocument()
        doc.setPageSize(QSizeF(paint.width(), paint.height()))
        doc.setDocumentMargin(0)

        def esc(x):
            return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        clinic = (self.context.repos.settings.get("clinic_name") or "").strip()
        head = f"<h1 style='margin:0'>{tr('admin.reports_pdf_title')}</h1>"
        head += f"<div style='color:#555'>{esc(scope)}</div>"
        if clinic:
            head += f"<div style='color:#777;font-size:10pt'>{esc(clinic)}</div>"
        red = "—" if totals["mean_pct_reduction"] is None else f"{totals['mean_pct_reduction']}%"
        slope = "—" if totals["mean_slope"] is None else totals["mean_slope"]
        summary = (
            f"<p><b>{tr('admin.reports_patients')}:</b> {totals['patients']} &nbsp;·&nbsp; "
            f"<b>{tr('admin.reports_sessions')}:</b> {totals['sessions']} &nbsp;·&nbsp; "
            f"<b>{tr('admin.reports_mean_reduction')}:</b> {red} &nbsp;·&nbsp; "
            f"<b>{tr('admin.reports_mean_slope')}:</b> {slope}</p>")
        er = " &nbsp; ".join(f"{esc(k)}: {v}" for k, v in end_reasons.items()) or "—"
        summary += f"<p style='color:#555'><b>{tr('admin.reports_end_reasons')}:</b> {er}</p>"

        cells = ["patient_code", "primary_substance", "n_sessions",
                 "mean_pct_reduction", "mean_slope", "last_session_at"]
        hdr = "".join(f"<th align='left' style='padding:4px 8px'>{esc(c)}</th>" for c in cells)
        body = ""
        for r in rows:
            tds = "".join(
                f"<td style='padding:3px 8px'>{esc('' if r.get(c) is None else r.get(c))}</td>"
                for c in cells)
            body += f"<tr>{tds}</tr>"
        table = (f"<table border='1' cellspacing='0' width='100%'><tr>{hdr}</tr>{body}</table>"
                 if rows else f"<p>{tr('admin.reports_empty')}</p>")
        doc.setHtml(f"{head}<hr>{summary}{table}")
        doc.print_(writer)

    # --- Storage page -------------------------------------------------------
    def _storage_page(self) -> QScrollArea:
        box, v = self._card("admin.tab_storage", "admin.storage_intro")
        cfg = self.context.config
        repos = self.context.repos
        db_path = Path(cfg.db_path)
        media_root = Path(cfg.media_root)
        db_size = db_path.stat().st_size if db_path.exists() else 0
        media_size = sum(p.stat().st_size for p in media_root.rglob("*") if p.is_file()) \
            if media_root.exists() else 0
        rows = [
            (tr("admin.storage_location"), str(db_path.parent)),
            (tr("admin.storage_db_size"), _fmt_size(db_size)),
            (tr("admin.storage_media_size"), _fmt_size(media_size)),
            (tr("admin.storage_patients"), str(repos.patients.count())),
            (tr("admin.storage_sessions"), str(repos.sessions.count())),
            (tr("admin.storage_clinicians"), str(repos.clinicians.count())),
        ]
        for label, value in rows:
            r = QHBoxLayout()
            lab = QLabel(label); lab.setObjectName("Muted")
            val = QLabel(value); val.setWordWrap(True)
            r.addWidget(lab); r.addSpacing(10); r.addWidget(val, 1)
            v.addLayout(r)
        open_btn = QPushButton(tr("admin.storage_open"))
        open_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(db_path.parent))))
        v.addWidget(open_btn)
        return self._page([box])

    # --- Audit page ---------------------------------------------------------
    def _audit_page(self) -> QScrollArea:
        box, v = self._card("admin.tab_audit", "admin.audit_intro")
        entries = self.context.repos.audit.list_recent(200)
        lst = QListWidget()
        if entries:
            for e in entries:
                lst.addItem(f"{e['ts']}  ·  {e['actor'] or '—'}  ·  {e['action']}  ·  {e['detail'] or ''}")
        else:
            lst.addItem(tr("admin.audit_empty"))
        lst.setMinimumHeight(320)
        v.addWidget(lst)
        return self._page([box])
