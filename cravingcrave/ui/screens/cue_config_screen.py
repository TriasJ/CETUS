"""Per-patient cue configuration: choose media, order by intensity, flag positives."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QWizard,
)

from ...domain.models import CueConfig
from ...services import substances as subs
from ...services.cue_weights import CueWeightLookup
from ...services.i18n import tr
from ...services.media_library import media_type_for
from ..context import AppContext
from ..responsive import adaptive_dialog_width, adaptive_margins

# Auxiliary (non-substance) media folders shown in the library picker.
_AUX_CATEGORY_KEYS = {"positive": "substance.positive", "sounds": "substance.sounds"}


def _category_label(context, cat: str) -> str:
    """Display label for a media category: aux folders via i18n, else substance name."""
    if cat in _AUX_CATEGORY_KEYS:
        return tr(_AUX_CATEGORY_KEYS[cat])
    return subs.display_name(context.repos.settings, cat)


class _LibraryDialog(QDialog):
    """Pick one or more files from a media category folder."""

    def __init__(self, context: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.setWindowTitle(tr("cueconfig.add_from_library"))
        self.setMinimumSize(min(460, adaptive_dialog_width()), 380)

        self.category = QComboBox()
        for cat in self.context.media.category_folders():
            self.category.addItem(_category_label(self.context, cat), cat)
        self.category.currentIndexChanged.connect(self._reload)

        self.files = QListWidget()
        self.files.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.empty = QLabel(tr("cueconfig.library_empty"))
        self.empty.setObjectName("Muted")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.category)
        layout.addWidget(self.empty)
        layout.addWidget(self.files, 1)
        layout.addWidget(buttons)
        self._reload()

    def _reload(self) -> None:
        self.files.clear()
        items = self.context.media.by_category(self.category.currentData())
        self.empty.setVisible(not items)
        for m in items:
            it = QListWidgetItem(f"{m.filename}  ({m.media_type})")
            it.setData(Qt.ItemDataRole.UserRole, m)
            self.files.addItem(it)

    def selected(self):
        return [i.data(Qt.ItemDataRole.UserRole) for i in self.files.selectedItems()]


class CueConfigScreen(QWidget):
    def __init__(self, window, context: AppContext, patient) -> None:
        super().__init__()
        self.window = window
        self.context = context
        self.patient = patient

        back = QPushButton(tr("common.back"))
        back.clicked.connect(lambda: window.show_patient(patient.id))
        title = QLabel(tr("cueconfig.title", code=patient.code))
        title.setObjectName("H1")
        header = QHBoxLayout()
        header.addWidget(back); header.addSpacing(10); header.addWidget(title); header.addStretch(1)

        intro = QLabel(tr("cueconfig.intro"))
        intro.setObjectName("Muted")
        intro.setWordWrap(True)

        self.list = QListWidget()
        self.empty = QLabel(tr("cueconfig.empty"))
        self.empty.setObjectName("Muted")

        add_lib = QPushButton(tr("cueconfig.add_from_library"))
        add_lib.setObjectName("Primary")
        add_lib.clicked.connect(self._add_from_library)
        add_files = QPushButton(tr("cueconfig.add_files"))
        add_files.clicked.connect(self._add_files)
        add_folder = QPushButton(tr("cueconfig.add_folder"))
        add_folder.setToolTip(tr("cueconfig.add_folder_tip"))
        add_folder.clicked.connect(self._add_folder)

        up = QPushButton(tr("cueconfig.move_up")); up.clicked.connect(lambda: self._move(-1))
        down = QPushButton(tr("cueconfig.move_down")); down.clicked.connect(lambda: self._move(1))
        toggle_en = QPushButton(tr("cueconfig.enabled")); toggle_en.clicked.connect(self._toggle_enabled)
        toggle_pos = QPushButton(tr("cueconfig.personal_reason")); toggle_pos.clicked.connect(self._toggle_personal)
        enable_all = QPushButton(tr("cueconfig.enable_all")); enable_all.clicked.connect(lambda: self._set_all_enabled(True))
        disable_all = QPushButton(tr("cueconfig.disable_all")); disable_all.clicked.connect(lambda: self._set_all_enabled(False))
        delete = QPushButton(tr("common.delete")); delete.setObjectName("Danger"); delete.clicked.connect(self._delete)

        suggest_w = QPushButton(tr("cueconfig.suggest_weights"))
        suggest_w.setToolTip(tr("cueconfig.weight_hint"))
        suggest_w.clicked.connect(self._suggest_weights)
        edit_weight = QPushButton(tr("cueconfig.edit_weight"))
        edit_weight.clicked.connect(self._edit_weight)

        import_wizard_btn = QPushButton(tr("cueconfig.import_wizard"))
        import_wizard_btn.clicked.connect(self._open_import_wizard)
        import_web_btn = QPushButton(tr("cueconfig.import_web"))
        import_web_btn.clicked.connect(self._open_import_web)

        buttons = [import_wizard_btn, import_web_btn, add_lib, add_files, add_folder,
                   up, down, suggest_w, edit_weight]
        # Adaptive ordering (opt-in): suggest a low→high craving order the clinician reviews & applies.
        if self.context.config.adaptive_ordering:
            suggest = QPushButton(tr("cueconfig.suggest_order"))
            suggest.setToolTip(tr("cueconfig.suggest_tip"))
            suggest.clicked.connect(self._suggest_order)
            export_order = QPushButton(tr("cueconfig.export_order"))
            export_order.clicked.connect(self._export_order)
            buttons += [suggest, export_order]
        buttons += [toggle_en, toggle_pos, enable_all, disable_all, delete]

        # Side button column: scrollable vertically, width adapts to content.
        # No maxWidth — let the buttons show their full labels. The body layout
        # gives stretch=1 to the cue list (left) and stretch=0 to the side column
        # so the buttons take only the space they need.
        side_widget = QWidget()
        side_layout = QVBoxLayout(side_widget)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(4)
        for b in buttons:
            side_layout.addWidget(b)
        side_layout.addStretch(1)
        side_scroll = QScrollArea()
        side_scroll.setWidget(side_widget)
        side_scroll.setWidgetResizable(True)
        side_scroll.setFrameShape(QFrame.Shape.NoFrame)

        body = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(self.empty)
        left.addWidget(self.list, 1)
        body.addLayout(left, 1)
        body.addWidget(side_scroll, 0)  # stretch=0: buttons take natural width

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*adaptive_margins())
        layout.addLayout(header)
        layout.addWidget(intro)
        layout.addLayout(body, 1)

        self._refresh()

    # --- data ---------------------------------------------------------------
    def _cues(self):
        return self.context.repos.cues.list_for_patient(self.patient.id)

    def _refresh(self) -> None:
        cues = self._cues()
        self.list.clear()
        self.empty.setVisible(not cues)
        missing_count = 0
        for c in cues:
            marks = []
            marks.append("✓" if c.enabled else "✗")
            if c.is_personal_reason:
                marks.append("★")
            if c.is_neutral:
                marks.append("◇")
            # Check if the media file still exists on disk.
            file_ok = self.context.media.absolute(c.media_path).exists()
            if not file_ok:
                marks.append("⚠")
                missing_count += 1
            weight_str = f"  w={c.craving_weight:.1f}" if c.craving_weight is not None else ""
            exposure_str = f" ×{c.exposure_count}" if c.exposure_count > 0 else ""
            label = (f"[{c.appetitive_rank}]{weight_str}{exposure_str} {c.media_path}"
                     f"  ({c.media_type})  {' '.join(marks)}")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, c.id)
            if not file_ok:
                item.setForeground(QColor("#e63946"))  # DANGER red
                item.setToolTip(tr("cueconfig.file_missing"))
            self.list.addItem(item)
        if missing_count:
            self.empty.setVisible(True)
            self.empty.setText(tr("cueconfig.files_missing", n=missing_count))

    def _selected_cue(self):
        item = self.list.currentItem()
        if item is None:
            return None
        cue_id = item.data(Qt.ItemDataRole.UserRole)
        return next((c for c in self._cues() if c.id == cue_id), None)

    # --- add ----------------------------------------------------------------
    def _next_rank(self) -> int:
        cues = self._cues()
        return (max((c.appetitive_rank for c in cues), default=-1)) + 1

    def _add_from_library(self) -> None:
        dialog = _LibraryDialog(self.context, self)
        if not dialog.exec():
            return
        rank = self._next_rank()
        weights = CueWeightLookup()
        existing_paths = {c.media_path for c in self._cues()}
        added = skipped = 0
        for m in sorted(dialog.selected(), key=lambda m: m.path):
            if m.path in existing_paths:
                skipped += 1
                continue
            w = weights.suggest(m.path)
            self.context.repos.cues.create(CueConfig(
                patient_id=self.patient.id, substance=m.substance, media_path=m.path,
                media_type=m.media_type, appetitive_rank=rank,
                is_personal_reason=(m.substance == "positive"),
                is_neutral=(m.substance == "neutral"),
                craving_weight=w,
            ))
            existing_paths.add(m.path)
            rank += 1
            added += 1
        self._refresh()
        if skipped:
            QMessageBox.information(self, tr("app.title"),
                                    tr("cueconfig.import_result", imported=added, skipped=skipped))

    _FILE_FILTER = ("Media (*.jpg *.jpeg *.png *.webp *.bmp *.gif "
                    "*.mp4 *.mov *.m4v *.avi *.mkv *.webm *.mp3 *.wav *.m4a *.aac *.ogg *.flac)")

    def _import_paths(self, paths) -> None:
        """Copy media files into the patient's substance folder and create cues.

        Shared by multi-file and folder import. Non-media files are skipped; files
        already present are reused in place. Duplicate paths are skipped.
        """
        category = self.patient.primary_substance or "alcohol"
        dest_dir = Path(self.context.config.media_root) / category
        dest_dir.mkdir(parents=True, exist_ok=True)
        existing_paths = {c.media_path for c in self._cues()}
        rank = self._next_rank()
        imported = skipped = 0
        for path in paths:
            src = Path(path)
            mtype = media_type_for(src)
            if mtype is None or not src.is_file():
                skipped += 1
                continue
            media_path = f"{category}/{src.name}"
            if media_path in existing_paths:
                skipped += 1
                continue
            dest = dest_dir / src.name
            try:
                if src.resolve() != dest.resolve():
                    shutil.copy2(src, dest)
            except OSError:
                skipped += 1
                continue
            self.context.repos.cues.create(CueConfig(
                patient_id=self.patient.id, substance=category,
                media_path=media_path, media_type=mtype, appetitive_rank=rank,
            ))
            existing_paths.add(media_path)
            rank += 1
            imported += 1
        self._refresh()
        QMessageBox.information(self, tr("app.title"),
                                tr("cueconfig.import_result", imported=imported, skipped=skipped))

    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, tr("cueconfig.add_files"), "", self._FILE_FILTER)
        if paths:
            self._import_paths(paths)

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("cueconfig.add_folder"))
        if not folder:
            return
        # Recurse into subfolders so a whole nested media tree imports in one action;
        # non-media files are filtered out by _import_paths.
        files = sorted(p for p in Path(folder).rglob("*") if p.is_file())
        self._import_paths(files)

    def _set_all_enabled(self, enabled: bool) -> None:
        for cue in self._cues():
            if cue.enabled != enabled:
                cue.enabled = enabled
                self.context.repos.cues.update(cue)
        self._refresh()

    # --- edit ---------------------------------------------------------------
    def _require_selected(self):
        cue = self._selected_cue()
        if cue is None:
            QMessageBox.information(self, tr("app.title"), tr("cueconfig.select_first"))
        return cue

    def _toggle_enabled(self) -> None:
        cue = self._require_selected()
        if cue:
            cue.enabled = not cue.enabled
            self.context.repos.cues.update(cue)
            self._refresh()

    def _toggle_personal(self) -> None:
        cue = self._require_selected()
        if cue:
            cue.is_personal_reason = not cue.is_personal_reason
            self.context.repos.cues.update(cue)
            self._refresh()

    def _delete(self) -> None:
        cue = self._require_selected()
        if cue:
            self.context.repos.cues.delete(cue.id)
            self._refresh()

    def _open_import_wizard(self) -> None:
        """Open the Import Images from Web wizard."""
        from .import_wizard import ImportWizard
        wizard = ImportWizard(self.context, self)
        if wizard.exec() == QWizard.DialogCode.Accepted:
            self._refresh()

    def _open_import_web(self) -> None:
        """Prompt which importer to open (Pexels images or YouTube video)."""
        import subprocess
        import sys as _sys

        from PySide6.QtWidgets import QInputDialog

        if getattr(_sys, "frozen", False):
            root = Path(_sys.executable).resolve().parent.parent
        else:
            root = Path(__file__).resolve().parents[3]

        tools_dir = root / "tools"
        pexels_ok = (tools_dir / "pexels_gui.py").exists()
        youtube_ok = (tools_dir / "youtube_gui.py").exists()
        if not pexels_ok and not youtube_ok:
            QMessageBox.information(
                self, tr("app.title"),
                tr("cueconfig.tools_unavailable"))
            return

        items = []
        if pexels_ok:
            items.append(tr("settings.import_web_button"))
        if youtube_ok:
            items.append(tr("settings.import_video_button"))

        if len(items) == 1:
            choice = items[0]
        else:
            choice, ok = QInputDialog.getItem(
                self, tr("settings.tools_title"), tr("settings.tools_hint"),
                items, 0, False)
            if not ok:
                return

        if pexels_ok and choice == tr("settings.import_web_button"):
            script = tools_dir / "pexels_gui.py"
        else:
            script = tools_dir / "youtube_gui.py"

        venv_python = root / ".venv" / "Scripts" / "python.exe"
        if not venv_python.exists():
            venv_python = root / ".venv" / "bin" / "python"
        if not venv_python.exists() and not getattr(_sys, "frozen", False):
            venv_python = Path(_sys.executable)
        if not venv_python.exists():
            QMessageBox.information(
                self, tr("app.title"),
                tr("cueconfig.tools_unavailable"))
            return
        env = dict(os.environ)
        env["CETUS_LOCALE"] = self.context.config.locale
        subprocess.Popen(
            [str(venv_python), str(script)], cwd=str(root), env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if _sys.platform == "win32" else 0,
        )

    def _edit_weight(self) -> None:
        """Manually adjust the craving weight of the selected cue."""
        cue = self._require_selected()
        if cue is None:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("cueconfig.edit_weight"))
        dlg.setMinimumWidth(min(360, adaptive_dialog_width()))
        form = QFormLayout()
        path_label = QLabel(f"<b>{Path(cue.media_path).name}</b>")
        weight_spin = QDoubleSpinBox()
        weight_spin.setRange(0.0, 10.0)
        weight_spin.setDecimals(1)
        weight_spin.setSingleStep(0.5)
        weight_spin.setValue(cue.craving_weight if cue.craving_weight is not None else 0.0)
        rank_spin = QDoubleSpinBox()
        rank_spin.setRange(0, 999)
        rank_spin.setDecimals(0)
        rank_spin.setValue(float(cue.appetitive_rank))
        form.addRow(tr("cueconfig.weight_label"), path_label)
        form.addRow(tr("cueconfig.weight_label") + " (0–10)", weight_spin)
        form.addRow("Rank", rank_spin)
        warning = QLabel(tr("cueconfig.edit_weight_warning"))
        warning.setWordWrap(True)
        warning.setStyleSheet("color:#8a5a00; font-size:12px; padding:6px; "
                              "background:#fef9e7; border-radius:4px;")
        form.addRow(warning)
        hint = QLabel(tr("cueconfig.weight_hint"))
        hint.setWordWrap(True); hint.setObjectName("Muted")
        form.addRow(hint)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
        v = QVBoxLayout(dlg); v.addLayout(form); v.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_weight = weight_spin.value()
        new_rank = int(rank_spin.value())
        changed = False
        if cue.craving_weight != new_weight:
            cue.craving_weight = new_weight
            changed = True
        if cue.appetitive_rank != new_rank:
            cue.appetitive_rank = new_rank
            changed = True
        if changed:
            self.context.repos.cues.update(cue)
            self._refresh()

    def _suggest_weights(self) -> None:
        """Populate craving_weight from the bundled research data for all cues that match."""
        weights = CueWeightLookup()
        if not weights.available():
            QMessageBox.information(self, tr("app.title"), tr("cueconfig.suggest_none"))
            return
        n = 0
        for cue in self._cues():
            w = weights.suggest(cue.media_path)
            if w is not None and cue.craving_weight != w:
                cue.craving_weight = w
                self.context.repos.cues.update(cue)
                n += 1
        self._refresh()
        QMessageBox.information(self, tr("app.title"), tr("cueconfig.weights_applied", n=n))

    def _suggest_order(self) -> None:
        """Preview a learned low→high craving order and let the clinician apply it (rewrites ranks)."""
        from ...services import cue_ranking
        order = cue_ranking.suggested_ranks(self.context.repos, self.patient.id)
        scores = {r["cue_id"]: r for r in cue_ranking.patient_cue_scores(self.context.repos, self.patient.id)}
        by_id = {c.id: c for c in self._cues()}
        ordered = [by_id[cid] for cid in order if cid in by_id]
        if not ordered:
            QMessageBox.information(self, tr("app.title"), tr("cueconfig.suggest_none"))
            return

        dlg = QDialog(self); dlg.setWindowTitle(tr("cueconfig.suggest_order"))
        dlg.setMinimumWidth(min(560, adaptive_dialog_width()))
        v = QVBoxLayout(dlg)
        intro = QLabel(tr("cueconfig.suggest_intro")); intro.setWordWrap(True)
        v.addWidget(intro)
        preview = QListWidget()
        for pos, c in enumerate(ordered, start=1):
            sc = scores.get(c.id, {})
            flag = f"  ·  {tr('cueconfig.suggest_lowdata')}" if sc.get("low_data") else ""
            preview.addItem(
                f"{pos}. {Path(c.media_path).name}  ·  {tr('cueconfig.suggest_score')} "
                f"{sc.get('score', 0):.1f}  (n={sc.get('n', 0)}){flag}")
        preview.setMinimumHeight(320)
        v.addWidget(preview)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(tr("cueconfig.suggest_apply"))
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        for rank, c in enumerate(ordered):
            if c.appetitive_rank != rank:
                c.appetitive_rank = rank
                self.context.repos.cues.update(c)
        self._refresh()
        QMessageBox.information(self, tr("app.title"), tr("cueconfig.suggest_applied"))

    def _export_order(self) -> None:
        """Export this patient's learned cue-order database (reactivity + ranks) as CSV."""
        from ...services import cue_ranking, export
        rows = cue_ranking.cue_order_rows(self.context.repos, self.patient.id)
        if not rows:
            QMessageBox.information(self, tr("app.title"), tr("cueconfig.suggest_none"))
            return
        default = str(Path(self.context.config.data_dir)
                      / export.safe_filename(self.patient.code, "cue_order"))
        path, _ = QFileDialog.getSaveFileName(self, tr("cueconfig.export_order"), default, "CSV (*.csv)")
        if not path:
            return
        export.export_cue_order(Path(path), rows)
        QMessageBox.information(self, tr("app.title"),
                               tr("cueconfig.order_exported", n=len(rows)))

    def _move(self, direction: int) -> None:
        cues = self._cues()
        cue = self._selected_cue()
        if cue is None:
            return
        idx = next((i for i, c in enumerate(cues) if c.id == cue.id), None)
        new_idx = idx + direction
        if idx is None or not (0 <= new_idx < len(cues)):
            return
        cues[idx], cues[new_idx] = cues[new_idx], cues[idx]
        for rank, c in enumerate(cues):
            if c.appetitive_rank != rank:
                c.appetitive_rank = rank
                self.context.repos.cues.update(c)
        self._refresh()
        self.list.setCurrentRow(new_idx)
