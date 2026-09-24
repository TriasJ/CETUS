"""Import Images from Web wizard.

A 6-page QWizard that guides the clinician through:
1. Welcome — explains what images are needed
2. Pexels API key setup (auto-skipped if valid key found)
3. Gemini API key setup (optional, auto-skipped if valid key found)
4. Download neutral images (main focus)
5. Learn: downloading substance cues (teaching + optional download)
6. Summary — what was downloaded, where to find the tool later

Auto-launches on first run of CETUS or when no neutral images exist.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from ...services.i18n import tr
from ..context import AppContext
from ..responsive import screen_size

# ---------------------------------------------------------------------------
# Pexels API client (stdlib only, no external deps)
# ---------------------------------------------------------------------------

def _load_pexels_key() -> str:
    """Load Pexels API key from env var or media/pexels.env.

    Accepts multiple file formats:
    - ``PEXELS_API_KEY=xxx`` (preferred)
    - ``key = xxx`` (legacy pexels.env format)
    - Any ``name=value`` line where value is >20 chars (likely an API key)
    """
    key = os.environ.get("PEXELS_API_KEY", "")
    if key:
        return key.strip()
    env_path = Path(__file__).resolve().parents[3] / "media" / "pexels.env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("PEXELS_API_KEY="):
                return line.split("=", 1)[1].strip()
            # Legacy format: any "key = value" line with a long value
            if "=" in line:
                val = line.split("=", 1)[1].strip()
                if len(val) > 20:
                    return val
    return ""


def _save_pexels_key(key: str) -> None:
    env_path = Path(__file__).resolve().parents[3] / "media" / "pexels.env"
    env_path.write_text(f"PEXELS_API_KEY={key}\n", encoding="utf-8")


def _load_gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key.strip()
    env_path = Path(__file__).resolve().parents[3] / "media" / "gemini.env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def _save_gemini_key(key: str) -> None:
    env_path = Path(__file__).resolve().parents[3] / "media" / "gemini.env"
    env_path.write_text(f"GEMINI_API_KEY={key}\n", encoding="utf-8")


def _verify_pexels_key(key: str) -> bool:
    """Test Pexels API key with a minimal request."""
    if not key:
        return False
    try:
        req = urllib.request.Request(
            "https://api.pexels.com/v1/search?query=test&per_page=1",
            headers={"Authorization": key},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def _pexels_search(key: str, query: str, page: int = 1, per_page: int = 15):
    """Search Pexels photos. Returns list of dicts with id, src, photographer, url."""
    url = (f"https://api.pexels.com/v1/search?"
           f"query={urllib.parse.quote(query)}&page={page}&per_page={per_page}")
    req = urllib.request.Request(url, headers={"Authorization": key})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    results = []
    for p in data.get("photos", []):
        results.append({
            "id": p["id"],
            "src_medium": p["src"]["medium"],
            "src_large": p["src"]["large"],
            "photographer": p.get("photographer", ""),
            "url": p.get("url", ""),
        })
    return results


def _download_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "CETUS/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _file_hashes(folder: Path) -> set[str]:
    """SHA-256 hashes of all files in folder."""
    hashes = set()
    if not folder.is_dir():
        return hashes
    for f in folder.iterdir():
        if f.is_file() and not f.name.startswith("_"):
            try:
                hashes.add(hashlib.sha256(f.read_bytes()).hexdigest())
            except OSError:
                pass
    return hashes


# ---------------------------------------------------------------------------
# Thumbnail download thread
# ---------------------------------------------------------------------------

class _ThumbWorker(QThread):
    """Download a single thumbnail in the background."""
    done = Signal(int, QPixmap)  # index, pixmap

    def __init__(self, index: int, url: str, parent=None):
        super().__init__(parent)
        self.index = index
        self.url = url

    def run(self):
        try:
            data = _download_bytes(self.url)
            pm = QPixmap()
            pm.loadFromData(data)
            self.done.emit(self.index, pm)
        except Exception:
            self.done.emit(self.index, QPixmap())


# ---------------------------------------------------------------------------
# Page 1 — Welcome
# ---------------------------------------------------------------------------

class _WelcomePage(QWizardPage):
    def __init__(self, context: AppContext, parent=None):
        super().__init__(parent)
        self.context = context
        self.setTitle(tr("import.welcome_title"))
        self.setSubTitle(tr("import.welcome_subtitle"))

        body = QLabel(tr("import.welcome_body"))
        body.setWordWrap(True)

        self._count = QLabel()
        self._count.setObjectName("Muted")

        v = QVBoxLayout(self)
        v.addWidget(body)
        v.addSpacing(12)
        v.addWidget(self._count)
        v.addStretch(1)

    def initializePage(self):
        n = len(self.context.media.by_category("neutral"))
        self._count.setText(tr("import.neutral_count", n=n))


# ---------------------------------------------------------------------------
# Page 2 — Pexels API Key
# ---------------------------------------------------------------------------

class _PexelsKeyPage(QWizardPage):
    PAGE_ID = 1

    def __init__(self, context: AppContext, parent=None):
        super().__init__(parent)
        self.context = context
        self._verified = False
        self._auto_skip = False

        self.setTitle(tr("import.pexels_title"))
        self.setSubTitle(tr("import.pexels_subtitle"))

        steps = QLabel(
            tr("import.pexels_step1") + "\n"
            + tr("import.pexels_step2") + "\n"
            + tr("import.pexels_step3")
        )
        steps.setWordWrap(True)

        open_btn = QPushButton(tr("import.open_pexels"))
        open_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://www.pexels.com/api/")))

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText(tr("import.api_key_label"))
        self._key_input.textChanged.connect(self._on_text_changed)

        verify_btn = QPushButton(tr("import.verify"))
        verify_btn.clicked.connect(self._verify)

        self._status = QLabel("")

        key_row = QHBoxLayout()
        key_row.addWidget(self._key_input, 1)
        key_row.addWidget(verify_btn)

        v = QVBoxLayout(self)
        v.addWidget(steps)
        v.addSpacing(8)
        v.addWidget(open_btn)
        v.addSpacing(12)
        v.addLayout(key_row)
        v.addWidget(self._status)
        v.addStretch(1)

    def initializePage(self):
        key = _load_pexels_key()
        if key:
            self._key_input.setText(key)
            self._verify()
            # Auto-skip if we found a key (even if verify failed due to no network).
            # The key is already saved — worst case it fails at search time.
            if key and len(key) > 10:
                self._auto_skip = True
                self._verified = True  # trust the saved key
                if not self._status.text():
                    self._status.setText(tr("import.key_valid"))
                    self._status.setStyleSheet("color:#2a9d8f; font-weight:bold;")
                from PySide6.QtCore import QTimer
                QTimer.singleShot(400, self._try_auto_advance)

    def _try_auto_advance(self):
        """Auto-click Next if the key was pre-verified."""
        if self._auto_skip and self._verified:
            wiz = self.wizard()
            if wiz is not None:
                wiz.next()

    def _on_text_changed(self):
        self._verified = False
        self._status.setText("")
        self.completeChanged.emit()

    def _verify(self):
        key = self._key_input.text().strip()
        if _verify_pexels_key(key):
            self._verified = True
            self._status.setText(tr("import.key_valid"))
            self._status.setStyleSheet("color:#2a9d8f; font-weight:bold;")
            _save_pexels_key(key)
        else:
            self._verified = False
            self._status.setText(tr("import.key_invalid"))
            self._status.setStyleSheet("color:#e63946; font-weight:bold;")
        self.completeChanged.emit()

    def isComplete(self):
        return self._verified


# ---------------------------------------------------------------------------
# Page 3 — Gemini API Key (optional)
# ---------------------------------------------------------------------------

class _GeminiKeyPage(QWizardPage):
    def __init__(self, context: AppContext, parent=None):
        super().__init__(parent)
        self.context = context
        self._has_key = False

        self.setTitle(tr("import.gemini_title"))
        self.setSubTitle(tr("import.gemini_subtitle"))

        info = QLabel(tr("import.gemini_subtitle"))
        info.setWordWrap(True)

        open_btn = QPushButton(tr("import.open_gemini"))
        open_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://aistudio.google.com/apikey")))

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText(tr("import.api_key_label"))

        save_btn = QPushButton(tr("common.save"))
        save_btn.clicked.connect(self._save_key)

        self._status = QLabel("")

        key_row = QHBoxLayout()
        key_row.addWidget(self._key_input, 1)
        key_row.addWidget(save_btn)

        v = QVBoxLayout(self)
        v.addWidget(info)
        v.addSpacing(8)
        v.addWidget(open_btn)
        v.addSpacing(12)
        v.addLayout(key_row)
        v.addWidget(self._status)
        v.addStretch(1)

    def initializePage(self):
        key = _load_gemini_key()
        if key:
            self._key_input.setText(key)
            self._has_key = True
            self._status.setText(tr("import.key_valid"))
            self._status.setStyleSheet("color:#2a9d8f;")
            # Auto-skip: Gemini key already configured
            from PySide6.QtCore import QTimer
            QTimer.singleShot(400, self._try_auto_advance)

    def _try_auto_advance(self):
        if self._has_key:
            wiz = self.wizard()
            if wiz is not None:
                wiz.next()

    def _save_key(self):
        key = self._key_input.text().strip()
        if key:
            _save_gemini_key(key)
            self._has_key = True
            self._status.setText(tr("import.key_saved"))
            self._status.setStyleSheet("color:#2a9d8f;")

    def isComplete(self):
        return True  # always completable — this page is optional


# ---------------------------------------------------------------------------
# Shared search + thumbnail grid mixin
# ---------------------------------------------------------------------------

class _SearchDownloadPage(QWizardPage):
    """Base for pages 4 and 5 — provides search bar, thumbnail grid, download."""

    def __init__(self, context: AppContext, category: str, parent=None):
        super().__init__(parent)
        self.context = context
        self._category = category
        self._results: list[dict] = []
        self._checks: list[QCheckBox] = []
        self._thumb_workers: list[_ThumbWorker] = []
        self._downloaded_count = 0
        self._skipped_count = 0

        # Search bar
        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("import.search_placeholder"))
        self._search_btn = QPushButton(tr("common.start"))
        self._search_btn.clicked.connect(self._do_search)
        self._search.returnPressed.connect(self._do_search)

        search_row = QHBoxLayout()
        search_row.addWidget(self._search, 1)
        search_row.addWidget(self._search_btn)

        # Thumbnail grid in scroll area
        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(8)

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._grid_widget)
        self._scroll.setWidgetResizable(True)
        self._scroll.setMinimumHeight(200)

        # Select / download controls
        sel_all = QPushButton(tr("import.select_all") if tr("import.select_all") != "import.select_all"
                              else "Select All")
        sel_all.clicked.connect(lambda: self._set_all_checked(True))
        desel_all = QPushButton(tr("import.deselect_all") if tr("import.deselect_all") != "import.deselect_all"
                                else "Deselect All")
        desel_all.clicked.connect(lambda: self._set_all_checked(False))
        self._download_btn = QPushButton(tr("import.download_selected", n=0))
        self._download_btn.setObjectName("Primary")
        self._download_btn.clicked.connect(self._do_download)
        self._download_btn.setEnabled(False)

        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(sel_all)
        ctrl_row.addWidget(desel_all)
        ctrl_row.addStretch(1)
        ctrl_row.addWidget(self._download_btn)

        self._progress = QProgressBar()
        self._progress.setVisible(False)

        self._status_label = QLabel("")
        self._status_label.setObjectName("Muted")

        # Compose — subclass adds header widgets before calling _build_layout
        self._search_row = search_row
        self._ctrl_row = ctrl_row

    def _build_layout(self, header_widgets: list[QWidget]):
        """Call from subclass __init__ after adding header widgets."""
        v = QVBoxLayout(self)
        for w in header_widgets:
            v.addWidget(w)
        v.addLayout(self._search_row)
        v.addWidget(self._scroll, 1)
        v.addLayout(self._ctrl_row)
        v.addWidget(self._progress)
        v.addWidget(self._status_label)

    def _do_search(self):
        query = self._search.text().strip()
        if not query:
            return
        key = _load_pexels_key()
        if not key:
            self._status_label.setText(tr("import.key_invalid"))
            return
        try:
            self._results = _pexels_search(key, query, per_page=15)
        except Exception as e:
            self._status_label.setText(str(e))
            return
        self._populate_grid()

    def _populate_grid(self):
        # Clear old
        for w in self._thumb_workers:
            w.quit()
        self._thumb_workers.clear()
        self._checks.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = 5
        for i, photo in enumerate(self._results):
            row, col = divmod(i, cols)
            card = QWidget()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(2, 2, 2, 2)
            cl.setSpacing(2)

            thumb = QLabel()
            thumb.setFixedSize(QSize(120, 90))
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setStyleSheet("background:#eef2f5; border-radius:4px;")
            thumb.setText("...")
            cl.addWidget(thumb)

            cb = QCheckBox(photo["photographer"][:18])
            cb.stateChanged.connect(self._update_download_count)
            cl.addWidget(cb)
            self._checks.append(cb)

            self._grid.addWidget(card, row, col)

            # Start async thumbnail download
            worker = _ThumbWorker(i, photo["src_medium"], self)
            worker.done.connect(self._on_thumb_loaded)
            worker.start()
            self._thumb_workers.append(worker)

        self._grid_widget.adjustSize()
        self._download_btn.setEnabled(bool(self._results))
        self._update_download_count()

    def _on_thumb_loaded(self, index: int, pixmap: QPixmap):
        if pixmap.isNull() or index >= self._grid.count():
            return
        item = self._grid.itemAt(index)
        if item and item.widget():
            card = item.widget()
            thumb = card.layout().itemAt(0).widget()
            if isinstance(thumb, QLabel):
                scaled = pixmap.scaled(120, 90, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                thumb.setPixmap(scaled)

    def _set_all_checked(self, checked: bool):
        for cb in self._checks:
            cb.setChecked(checked)

    def _update_download_count(self):
        n = sum(1 for cb in self._checks if cb.isChecked())
        self._download_btn.setText(tr("import.download_selected", n=n))

    def _do_download(self):
        key = _load_pexels_key()
        if not key:
            return
        selected = [(i, self._results[i]) for i, cb in enumerate(self._checks) if cb.isChecked()]
        if not selected:
            return

        folder = self.context.config.media_root / self._category
        folder.mkdir(parents=True, exist_ok=True)
        existing_hashes = _file_hashes(folder)

        self._progress.setVisible(True)
        self._progress.setMaximum(len(selected))
        self._downloaded_count = 0
        self._skipped_count = 0

        for idx, (_, photo) in enumerate(selected):
            self._progress.setValue(idx)
            try:
                data = _download_bytes(photo["src_large"])
                h = hashlib.sha256(data).hexdigest()
                if h in existing_hashes:
                    self._skipped_count += 1
                    continue

                # Name: px_{query_slug}_{id}.jpg
                query_slug = urllib.parse.quote(self._search.text().strip()[:20], safe="")
                ext = "jpg"
                name = f"px_{query_slug}_{photo['id']}.{ext}"
                dest = folder / name
                if dest.exists():
                    self._skipped_count += 1
                    continue

                dest.write_bytes(data)
                existing_hashes.add(h)
                self._downloaded_count += 1

                # Append to _licenses.csv
                lic_path = folder / "_licenses.csv"
                if not lic_path.exists():
                    lic_path.write_text("file,license,version,creator,source_url\n",
                                        encoding="utf-8")
                with lic_path.open("a", encoding="utf-8") as f:
                    f.write(f'{name},Pexels License,N/A,{photo["photographer"]},'
                            f'{photo["url"]}\n')
            except Exception:
                pass

        self._progress.setValue(len(selected))
        self._progress.setVisible(False)
        parts = []
        if self._downloaded_count:
            parts.append(tr("import.download_done", n=self._downloaded_count))
        if self._skipped_count:
            parts.append(tr("import.skipped_dup", n=self._skipped_count))
        self._status_label.setText(" · ".join(parts) if parts else "")


# ---------------------------------------------------------------------------
# Page 4 — Download Neutral Images
# ---------------------------------------------------------------------------

class _NeutralDownloadPage(_SearchDownloadPage):
    def __init__(self, context: AppContext, parent=None):
        super().__init__(context, "neutral", parent)
        self.setTitle(tr("import.neutral_title"))
        self.setSubTitle(tr("import.neutral_subtitle"))

        explain = QLabel(tr("import.neutral_explain"))
        explain.setWordWrap(True)

        self._neutral_count = QLabel()
        self._neutral_count.setObjectName("Muted")

        self._search.setText("everyday objects")
        self._build_layout([explain, self._neutral_count])

    def initializePage(self):
        n = len(self.context.media.by_category("neutral"))
        self._neutral_count.setText(tr("import.neutral_count", n=n))


# ---------------------------------------------------------------------------
# Page 5 — Learn: Downloading Substance Cues
# ---------------------------------------------------------------------------

class _SubstanceDownloadPage(_SearchDownloadPage):
    def __init__(self, context: AppContext, parent=None):
        super().__init__(context, "alcohol", parent)
        self.setTitle(tr("import.substance_title"))
        self.setSubTitle(tr("import.substance_subtitle"))

        explain = QLabel(tr("import.substance_tips"))
        explain.setWordWrap(True)

        # Substance selector
        self._substance = QComboBox()
        from ...services import substances as subs
        for value, label in subs.available_substances(context.repos.settings):
            self._substance.addItem(label, value)
        self._substance.currentIndexChanged.connect(self._on_substance_changed)

        sub_row = QHBoxLayout()
        sub_label = QLabel(tr("import.select_substance"))
        sub_row.addWidget(sub_label)
        sub_row.addWidget(self._substance, 1)

        sub_widget = QWidget()
        sub_widget.setLayout(sub_row)

        self._build_layout([explain, sub_widget])

    def _on_substance_changed(self):
        self._category = self._substance.currentData() or "alcohol"


# ---------------------------------------------------------------------------
# Page 6 — Summary
# ---------------------------------------------------------------------------

class _SummaryPage(QWizardPage):
    def __init__(self, context: AppContext, parent=None):
        super().__init__(parent)
        self.context = context
        self.setTitle(tr("import.summary_title"))

        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._summary.setTextFormat(Qt.TextFormat.RichText)

        body = QLabel(tr("import.summary_body"))
        body.setWordWrap(True)
        body.setObjectName("Muted")

        v = QVBoxLayout(self)
        v.addWidget(self._summary)
        v.addSpacing(12)
        v.addWidget(body)
        v.addStretch(1)

    def initializePage(self):
        wizard = self.wizard()
        neutral_page = wizard._neutral_page
        substance_page = wizard._substance_page

        rows = []
        if neutral_page._downloaded_count:
            rows.append(f"<tr><td>Neutral</td><td><b>{neutral_page._downloaded_count}</b></td></tr>")
        if substance_page._downloaded_count:
            cat = substance_page._category
            rows.append(f"<tr><td>{cat.title()}</td><td><b>{substance_page._downloaded_count}</b></td></tr>")
        skipped = neutral_page._skipped_count + substance_page._skipped_count
        if skipped:
            rows.append(f"<tr><td>{tr('import.skipped_dup', n=skipped)}</td><td></td></tr>")

        if rows:
            html = (f"<p><b>{tr('import.summary_downloaded')}</b></p>"
                    f"<table style='margin:8px 0;'>{''.join(rows)}</table>")
        else:
            html = f"<p>{tr('import.summary_downloaded')} 0</p>"
        self._summary.setText(html)

        # Mark wizard complete
        self.context.repos.settings.set("import_wizard_complete", "1")


# ---------------------------------------------------------------------------
# Main Wizard
# ---------------------------------------------------------------------------

class ImportWizard(QWizard):
    """Six-page Import Images from Web wizard."""

    def __init__(self, context: AppContext, parent=None):
        super().__init__(parent)
        self.context = context

        self.setWindowTitle(tr("import.welcome_title"))
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        sw, sh = screen_size()
        w = min(820, max(600, int(sw * 0.75)))
        h = min(660, max(480, int(sh * 0.75)))
        self.resize(w, h)
        self.setMinimumSize(min(600, sw - 40), min(480, sh - 40))

        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.setButtonText(QWizard.WizardButton.BackButton, tr("common.back"))
        self.setButtonText(QWizard.WizardButton.NextButton, tr("common.next"))
        self.setButtonText(QWizard.WizardButton.FinishButton, tr("common.finish"))
        self.setButtonText(QWizard.WizardButton.CancelButton, tr("common.cancel"))

        self._welcome = _WelcomePage(context)
        self._pexels_key = _PexelsKeyPage(context)
        self._gemini_key = _GeminiKeyPage(context)
        self._neutral_page = _NeutralDownloadPage(context)
        self._substance_page = _SubstanceDownloadPage(context)
        self._summary = _SummaryPage(context)

        self.addPage(self._welcome)       # 0
        self.addPage(self._pexels_key)     # 1
        self.addPage(self._gemini_key)     # 2
        self.addPage(self._neutral_page)   # 3
        self.addPage(self._substance_page) # 4
        self.addPage(self._summary)        # 5
