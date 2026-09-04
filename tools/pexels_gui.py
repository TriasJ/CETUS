"""PySide6 GUI for browsing and downloading Pexels stock media into the media library.

Search photos or videos, preview thumbnails, select what to download, and save
into the chosen media/<category>/ folder.  License metadata is appended to
``_licenses.csv`` automatically.

    pip install PySide6           # (already in the project venv)
    python tools/pexels_gui.py

Requires a Pexels API key in env var PEXELS_API_KEY or in media/pexels.env.
Get a free key at https://www.pexels.com/api/

IMPORTANT: The Pexels License permits free commercial and research use.
API users MUST credit the photographer.  Always review media for clinical
appropriateness before using with patients.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, QThread, Qt, Signal
from PySide6.QtGui import QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent
MEDIA_ROOT = PROJECT_ROOT / "media"

CATEGORIES = [
    d.name
    for d in sorted(MEDIA_ROOT.iterdir())
    if d.is_dir() and not d.name.startswith(".")
] if MEDIA_ROOT.is_dir() else ["alcohol", "cigarettes", "cocaina", "meth", "positive", "sounds"]

# ---------------------------------------------------------------------------
# Palette (mirrors cravingcrave/ui/theme.py)
# ---------------------------------------------------------------------------
PRIMARY = "#2a9d8f"
PRIMARY_DARK = "#21867a"
DANGER = "#e63946"
TEXT = "#1f2933"
MUTED = "#5f6b7a"
SURFACE = "#ffffff"
BG = "#f4f6f8"

# ---------------------------------------------------------------------------
# API constants
# ---------------------------------------------------------------------------
PHOTO_API = "https://api.pexels.com/v1/search"
VIDEO_API = "https://api.pexels.com/v1/videos/search"
USER_AGENT = "CETUS-ContentTool/0.1 (clinical CET media; respectful use)"

PHOTO_SIZES = ["large", "large2x", "original", "medium", "small"]
VIDEO_QUALITIES = [("HD (720p)", "hd", 720), ("Full HD (1080p)", "fhd", 1080),
                   ("SD (480p)", "sd", 480), ("UHD (4K)", "uhd", 2160)]
ORIENTATIONS = ["Any", "Landscape", "Portrait", "Square"]
THUMB_W, THUMB_H = 160, 110
GRID_COLS = 4


# ---------------------------------------------------------------------------
# API key
# ---------------------------------------------------------------------------

def _load_api_key() -> str | None:
    key = os.environ.get("PEXELS_API_KEY")
    if key:
        return key.strip()
    env_file = MEDIA_ROOT / "pexels.env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                return line.split("=", 1)[1].strip()
    return None


# ---------------------------------------------------------------------------
# Workers (QThread)
# ---------------------------------------------------------------------------

class SearchWorker(QThread):
    """Search Pexels API in background."""

    results_ready = Signal(list, dict)  # (items, response_meta)
    rate_info = Signal(str)
    error = Signal(str)

    def __init__(self, api_key: str, query: str, media_type: str,
                 orientation: str, page: int, per_page: int) -> None:
        super().__init__()
        self.api_key = api_key
        self.query = query
        self.media_type = media_type
        self.orientation = orientation
        self.page = page
        self.per_page = per_page

    def run(self) -> None:
        try:
            base = PHOTO_API if self.media_type == "photo" else VIDEO_API
            params: dict[str, str | int] = {
                "query": self.query,
                "per_page": self.per_page,
                "page": self.page,
            }
            if self.orientation and self.orientation != "any":
                params["orientation"] = self.orientation

            url = f"{base}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Authorization": self.api_key,
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                headers = {k.lower(): v for k, v in resp.getheaders()}
                data = json.loads(resp.read().decode("utf-8"))

            remaining = headers.get("x-ratelimit-remaining", "?")
            limit = headers.get("x-ratelimit-limit", "?")
            self.rate_info.emit(f"Rate limit: {remaining}/{limit} remaining")

            key = "photos" if self.media_type == "photo" else "videos"
            items = data.get(key, [])
            meta = {
                "total_results": data.get("total_results", 0),
                "page": data.get("page", 1),
                "per_page": data.get("per_page", self.per_page),
                "next_page": data.get("next_page"),
                "prev_page": data.get("prev_page"),
            }
            self.results_ready.emit(items, meta)

        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                self.error.emit("Invalid API key (HTTP 401). Check your key.")
            elif exc.code == 429:
                self.error.emit("Rate limit exceeded (HTTP 429). Wait and retry.")
            else:
                self.error.emit(f"HTTP error {exc.code}: {exc.reason}")
        except Exception as exc:
            self.error.emit(str(exc))


class ThumbnailWorker(QThread):
    """Download thumbnail images for preview."""

    thumbnail_ready = Signal(int, QPixmap)  # (index, pixmap)
    finished = Signal()

    def __init__(self, urls: list[tuple[int, str]]) -> None:
        super().__init__()
        self.urls = urls

    def run(self) -> None:
        for idx, url in self.urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = resp.read()
                img = QImage()
                img.loadFromData(QByteArray(data))
                if not img.isNull():
                    pm = QPixmap.fromImage(img).scaled(
                        THUMB_W, THUMB_H,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.thumbnail_ready.emit(idx, pm)
            except Exception:
                pass  # placeholder stays
        self.finished.emit()


class DownloadWorker(QThread):
    """Download selected media items."""

    log = Signal(str)
    progress = Signal(int)
    finished_ok = Signal(int)
    finished_err = Signal(str)

    def __init__(self, items: list[dict], media_type: str, save_dir: Path,
                 slug: str, size_key: str, video_quality: int) -> None:
        super().__init__()
        self.items = items
        self.media_type = media_type
        self.save_dir = save_dir
        self.slug = slug
        self.size_key = size_key
        self.video_quality = video_quality
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            self.save_dir.mkdir(parents=True, exist_ok=True)
            total = len(self.items)
            rows: list[list[str]] = []
            saved = 0

            for i, item in enumerate(self.items, start=1):
                if self._cancelled:
                    self.log.emit("Download cancelled.")
                    break

                self.progress.emit(int((i - 1) / total * 100))

                if self.media_type == "photo":
                    ok, row = self._download_photo(item, saved + 1)
                else:
                    ok, row = self._download_video(item, saved + 1)

                if ok and row:
                    saved += 1
                    rows.append(row)

            # Write licenses
            if rows:
                lic = self.save_dir / "_licenses.csv"
                write_header = not lic.exists()
                with open(lic, "a", newline="", encoding="utf-8") as fh:
                    w = csv.writer(fh)
                    if write_header:
                        w.writerow(["file", "license", "creator", "source_url"])
                    w.writerows(rows)

            self.progress.emit(100)
            self.finished_ok.emit(saved)

        except Exception as exc:
            self.finished_err.emit(str(exc))

    def _download_photo(self, photo: dict, num: int) -> tuple[bool, list[str] | None]:
        src_url = photo.get("src", {}).get(self.size_key)
        if not src_url:
            self.log.emit(f"  ! no {self.size_key!r} URL for photo {photo.get('id')}")
            return False, None

        ext = ".jpg"
        url_path = urllib.parse.urlparse(src_url).path
        if "." in url_path:
            ext = "." + url_path.rsplit(".", 1)[-1].split("?")[0]
            if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                ext = ".jpg"

        dest = self.save_dir / f"px_{self.slug}_{num:02d}{ext}"
        photographer = photo.get("photographer", "")
        self.log.emit(f"Downloading {dest.name} (by {photographer})…")

        req = urllib.request.Request(src_url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                dest.write_bytes(resp.read())
            self.log.emit(f"  [ok] {dest.name}")
            return True, [dest.name, "Pexels License", photographer, photo.get("url", "")]
        except Exception as exc:
            self.log.emit(f"  ! failed: {exc}")
            return False, None

    def _download_video(self, video: dict, num: int) -> tuple[bool, list[str] | None]:
        mp4s = [vf for vf in video.get("video_files", [])
                if vf.get("file_type") == "video/mp4"]
        if not mp4s:
            self.log.emit(f"  ! no MP4 for video {video.get('id')}")
            return False, None

        mp4s.sort(key=lambda vf: vf.get("height", 0), reverse=True)
        chosen = None
        for vf in mp4s:
            if vf.get("height", 0) <= self.video_quality:
                chosen = vf
                break
        if chosen is None:
            chosen = mp4s[-1]

        dl_url = chosen["link"]
        res = f"{chosen.get('width', '?')}x{chosen.get('height', '?')}"
        dest = self.save_dir / f"px_{self.slug}_{num:02d}.mp4"
        creator = video.get("user", {}).get("name", "")
        self.log.emit(f"Downloading {dest.name} ({res}, by {creator})…")

        req = urllib.request.Request(dl_url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                dest.write_bytes(resp.read())
            self.log.emit(f"  [ok] {dest.name}")
            return True, [dest.name, "Pexels License", creator, video.get("url", "")]
        except Exception as exc:
            self.log.emit(f"  ! failed: {exc}")
            return False, None


# ---------------------------------------------------------------------------
# Result card widget
# ---------------------------------------------------------------------------

class ResultCard(QFrame):
    """A single search-result thumbnail + info + checkbox."""

    def __init__(self, index: int, info_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self.setObjectName("ResultCard")
        self.setFixedSize(THUMB_W + 16, THUMB_H + 60)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 4)
        layout.setSpacing(3)

        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(THUMB_W, THUMB_H)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet("background-color: #e1e6eb; border-radius: 4px;")
        self.thumb_label.setText("⏳")
        layout.addWidget(self.thumb_label)

        self.info_label = QLabel(info_text)
        self.info_label.setObjectName("Muted")
        self.info_label.setWordWrap(True)
        self.info_label.setMaximumHeight(20)
        font = self.info_label.font()
        font.setPointSize(8)
        self.info_label.setFont(font)
        layout.addWidget(self.info_label)

        self.checkbox = QCheckBox("Select")
        layout.addWidget(self.checkbox)

    def set_thumbnail(self, pixmap: QPixmap) -> None:
        self.thumb_label.setPixmap(pixmap)
        self.thumb_label.setText("")

    def is_selected(self) -> bool:
        return self.checkbox.isChecked()

    def set_selected(self, selected: bool) -> None:
        self.checkbox.setChecked(selected)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class PexelsDownloader(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CETUS — Pexels Media Downloader")
        self.setMinimumWidth(740)

        self._api_key = _load_api_key()
        self._custom_folder: Path | None = None
        self._current_items: list[dict] = []
        self._current_meta: dict = {}
        self._cards: list[ResultCard] = []
        self._search_worker: SearchWorker | None = None
        self._thumb_worker: ThumbnailWorker | None = None
        self._download_worker: DownloadWorker | None = None

        self._build_ui()
        self._apply_style()

        if not self._api_key:
            QMessageBox.critical(
                self, "API Key Missing",
                "Pexels API key not found.\n\n"
                "Set PEXELS_API_KEY environment variable or place the key in\n"
                "media/pexels.env\n\n"
                "Get a free key at https://www.pexels.com/api/",
            )

    # -- UI ----------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # Header
        title = QLabel("Pexels Media Downloader")
        title.setObjectName("H2")
        root.addWidget(title)

        subtitle = QLabel(
            "Search and download stock photos & videos from Pexels.  "
            "The Pexels License permits free research/commercial use — "
            "API users must credit the photographer."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # Search row
        search_row = QHBoxLayout()
        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("e.g. beer glass, bar scene, cigarette…")
        self.query_edit.returnPressed.connect(self._on_search)
        search_row.addWidget(self.query_edit, stretch=1)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Photos", "Videos"])
        self.type_combo.setFixedWidth(90)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        search_row.addWidget(self.type_combo)

        self.search_btn = QPushButton("Search")
        self.search_btn.setObjectName("Primary")
        self.search_btn.setFixedWidth(80)
        self.search_btn.clicked.connect(self._on_search)
        search_row.addWidget(self.search_btn)
        root.addLayout(search_row)

        # Filters row
        filter_row = QHBoxLayout()

        filter_row.addWidget(QLabel("Orientation:"))
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItems(ORIENTATIONS)
        self.orientation_combo.setFixedWidth(100)
        filter_row.addWidget(self.orientation_combo)

        filter_row.addWidget(QLabel("Photo size:"))
        self.size_combo = QComboBox()
        self.size_combo.addItems(PHOTO_SIZES)
        self.size_combo.setFixedWidth(100)
        filter_row.addWidget(self.size_combo)

        self.quality_label = QLabel("Video quality:")
        filter_row.addWidget(self.quality_label)
        self.quality_combo = QComboBox()
        for label, _, _ in VIDEO_QUALITIES:
            self.quality_combo.addItem(label)
        self.quality_combo.setFixedWidth(120)
        filter_row.addWidget(self.quality_combo)
        self.quality_label.hide()
        self.quality_combo.hide()

        filter_row.addStretch()
        root.addLayout(filter_row)

        # Rate limit
        self.rate_label = QLabel("Rate limit: —")
        self.rate_label.setObjectName("Muted")
        root.addWidget(self.rate_label)

        # Results scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumHeight(240)
        self.results_container = QWidget()
        self.results_layout = QGridLayout(self.results_container)
        self.results_layout.setSpacing(8)
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.results_container)
        root.addWidget(self.scroll, stretch=1)

        # Pagination
        page_row = QHBoxLayout()
        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self._on_prev_page)
        page_row.addWidget(self.prev_btn)
        self.page_label = QLabel("")
        self.page_label.setObjectName("Muted")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_row.addWidget(self.page_label, stretch=1)
        self.next_btn = QPushButton("Next →")
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._on_next_page)
        page_row.addWidget(self.next_btn)
        root.addLayout(page_row)

        # Download settings row
        dl_row = QHBoxLayout()
        dl_row.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems(CATEGORIES)
        self.category_combo.currentTextChanged.connect(lambda _: self._update_folder())
        dl_row.addWidget(self.category_combo)

        dl_row.addWidget(QLabel("Folder:"))
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self._update_folder()
        dl_row.addWidget(self.folder_edit, stretch=1)
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_folder)
        dl_row.addWidget(browse_btn)
        root.addLayout(dl_row)

        # Action buttons
        btn_row = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(lambda: self._set_all_selected(True))
        btn_row.addWidget(self.select_all_btn)
        self.select_none_btn = QPushButton("Select None")
        self.select_none_btn.clicked.connect(lambda: self._set_all_selected(False))
        btn_row.addWidget(self.select_none_btn)
        btn_row.addStretch()

        self.download_btn = QPushButton("  Download Selected  ")
        self.download_btn.setObjectName("Primary")
        self.download_btn.clicked.connect(self._on_download)
        btn_row.addWidget(self.download_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("Danger")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.cancel_btn)
        root.addLayout(btn_row)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        root.addWidget(self.progress_bar)

        # Log
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(140)
        self.log_view.setPlaceholderText("Download log will appear here…")
        root.addWidget(self.log_view)

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {BG};
                color: {TEXT};
                font-family: "Segoe UI";
                font-size: 14px;
            }}
            QLabel#H2 {{
                font-size: 21px;
                font-weight: 600;
                color: #14303a;
            }}
            QLabel#Muted {{
                color: {MUTED};
            }}
            QLabel#RateDanger {{
                color: {DANGER};
                font-weight: 600;
            }}
            QLineEdit, QComboBox {{
                background-color: {SURFACE};
                border: 1px solid #c5ced6;
                border-radius: 7px;
                padding: 7px 10px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: {PRIMARY};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QPushButton {{
                background-color: {SURFACE};
                border: 1px solid #c5ced6;
                border-radius: 9px;
                padding: 8px 14px;
                min-height: 20px;
            }}
            QPushButton:hover {{ background-color: #eef2f5; }}
            QPushButton:disabled {{ color: #9aa6b1; background-color: #f0f2f4; }}
            QPushButton#Primary {{
                background-color: {PRIMARY};
                color: #ffffff;
                border: none;
                font-weight: 600;
            }}
            QPushButton#Primary:hover {{ background-color: {PRIMARY_DARK}; }}
            QPushButton#Primary:disabled {{ background-color: #a7d3cc; color: #eef7f5; }}
            QPushButton#Danger {{ color: #c92f3b; border-color: #e6a3a8; }}
            QPushButton#Danger:disabled {{ color: #ccc; border-color: #ddd; }}
            QCheckBox {{ spacing: 6px; }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 2px solid #c5ced6; border-radius: 3px;
                background-color: {SURFACE};
            }}
            QCheckBox::indicator:checked {{
                background-color: {PRIMARY}; border-color: {PRIMARY};
            }}
            QScrollArea {{
                background-color: {SURFACE};
                border: 1px solid #e1e6eb;
                border-radius: 7px;
            }}
            QFrame#ResultCard {{
                background-color: {SURFACE};
                border: 1px solid #e9ecef;
                border-radius: 8px;
            }}
            QFrame#ResultCard:hover {{
                border-color: {PRIMARY};
            }}
            QProgressBar {{
                background-color: #e1e6eb;
                border: none; border-radius: 6px;
                height: 14px; text-align: center; font-size: 11px;
            }}
            QProgressBar::chunk {{
                background-color: {PRIMARY}; border-radius: 6px;
            }}
            QTextEdit {{
                background-color: {SURFACE};
                border: 1px solid #e1e6eb;
                border-radius: 7px;
                padding: 6px;
                font-family: "Consolas", "Courier New", monospace;
                font-size: 12px;
            }}
        """)

    # -- helpers -----------------------------------------------------------

    def _current_save_dir(self) -> Path:
        if self._custom_folder is not None:
            return self._custom_folder
        return MEDIA_ROOT / self.category_combo.currentText()

    def _update_folder(self) -> None:
        self._custom_folder = None
        self.folder_edit.setText(str(self._current_save_dir()))

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Choose save folder", str(self._current_save_dir()),
        )
        if folder:
            self._custom_folder = Path(folder)
            self.folder_edit.setText(str(self._custom_folder))

    def _set_all_selected(self, selected: bool) -> None:
        for card in self._cards:
            card.set_selected(selected)

    def _clear_results(self) -> None:
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()
        self._current_items.clear()

    def _media_type(self) -> str:
        return "photo" if self.type_combo.currentIndex() == 0 else "video"

    def _on_type_changed(self) -> None:
        is_photo = self.type_combo.currentIndex() == 0
        self.size_combo.setVisible(is_photo)
        # find the label before size_combo
        self.quality_label.setVisible(not is_photo)
        self.quality_combo.setVisible(not is_photo)

    # -- search ------------------------------------------------------------

    def _on_search(self, page: int = 1) -> None:
        query = self.query_edit.text().strip()
        if not query:
            QMessageBox.warning(self, "Missing query", "Enter a search query.")
            return
        if not self._api_key:
            QMessageBox.critical(self, "API Key Missing", "No Pexels API key configured.")
            return

        self.search_btn.setEnabled(False)
        self.search_btn.setText("…")
        self._clear_results()

        orientation = self.orientation_combo.currentText().lower()
        if orientation == "any":
            orientation = ""

        self._search_worker = SearchWorker(
            api_key=self._api_key,
            query=query,
            media_type=self._media_type(),
            orientation=orientation,
            page=page,
            per_page=20,
        )
        self._search_worker.results_ready.connect(self._on_results)
        self._search_worker.rate_info.connect(self._on_rate_info)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()

    def _on_results(self, items: list[dict], meta: dict) -> None:
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Search")
        self._current_items = items
        self._current_meta = meta

        if not items:
            self.page_label.setText("No results found.")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return

        # Pagination info
        total = meta.get("total_results", 0)
        page = meta.get("page", 1)
        per_page = meta.get("per_page", 20)
        self.page_label.setText(f"Page {page} — {total} total results")
        self.prev_btn.setEnabled(meta.get("prev_page") is not None)
        self.next_btn.setEnabled(meta.get("next_page") is not None)

        # Build result cards
        is_photo = self._media_type() == "photo"
        thumb_urls: list[tuple[int, str]] = []

        for i, item in enumerate(items):
            if is_photo:
                photographer = item.get("photographer", "Unknown")
                info = photographer
                thumb_url = item.get("src", {}).get("tiny", "")
            else:
                creator = item.get("user", {}).get("name", "Unknown")
                duration = item.get("duration", 0)
                info = f"{creator} ({duration}s)"
                thumb_url = item.get("image", "")

            card = ResultCard(i, info)
            self._cards.append(card)
            row, col = divmod(i, GRID_COLS)
            self.results_layout.addWidget(card, row, col)

            if thumb_url:
                thumb_urls.append((i, thumb_url))

        # Load thumbnails async
        if thumb_urls:
            self._thumb_worker = ThumbnailWorker(thumb_urls)
            self._thumb_worker.thumbnail_ready.connect(self._on_thumbnail)
            self._thumb_worker.start()

    def _on_thumbnail(self, index: int, pixmap: QPixmap) -> None:
        if 0 <= index < len(self._cards):
            self._cards[index].set_thumbnail(pixmap)

    def _on_rate_info(self, text: str) -> None:
        self.rate_label.setText(text)
        # Parse remaining for danger coloring
        m = re.search(r"(\d+)/", text)
        if m and int(m.group(1)) < 10:
            self.rate_label.setObjectName("RateDanger")
        else:
            self.rate_label.setObjectName("Muted")
        self.rate_label.setStyleSheet(self.rate_label.styleSheet())  # force refresh

    def _on_search_error(self, msg: str) -> None:
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Search")
        QMessageBox.critical(self, "Search failed", msg)

    # -- pagination --------------------------------------------------------

    def _on_prev_page(self) -> None:
        page = self._current_meta.get("page", 1)
        if page > 1:
            self._on_search(page=page - 1)

    def _on_next_page(self) -> None:
        page = self._current_meta.get("page", 1)
        self._on_search(page=page + 1)

    # -- download ----------------------------------------------------------

    def _on_download(self) -> None:
        selected_indices = [c.index for c in self._cards if c.is_selected()]
        if not selected_indices:
            QMessageBox.warning(self, "Nothing selected", "Select at least one item to download.")
            return

        selected_items = [self._current_items[i] for i in selected_indices]
        query = self.query_edit.text().strip()
        slug = "".join(c if c.isalnum() else "-" for c in query.lower())[:24].strip("-") or "pexels"

        # Video quality
        vq_idx = self.quality_combo.currentIndex()
        _, _, video_max_h = VIDEO_QUALITIES[vq_idx]

        self.log_view.clear()
        self.progress_bar.setValue(0)
        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        self._download_worker = DownloadWorker(
            items=selected_items,
            media_type=self._media_type(),
            save_dir=self._current_save_dir(),
            slug=slug,
            size_key=self.size_combo.currentText().lower().replace(" ", ""),
            video_quality=video_max_h,
        )
        self._download_worker.log.connect(self._on_log)
        self._download_worker.progress.connect(self.progress_bar.setValue)
        self._download_worker.finished_ok.connect(self._on_download_done)
        self._download_worker.finished_err.connect(self._on_download_error)
        self._download_worker.start()

    def _on_cancel(self) -> None:
        if self._download_worker and self._download_worker.isRunning():
            self._download_worker.cancel()
            self._on_log("Cancelling…")

    def _on_log(self, text: str) -> None:
        self.log_view.append(text)
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_download_done(self, count: int) -> None:
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setValue(100)
        self._on_log(f"\n✅ Downloaded {count} file(s).")
        QMessageBox.information(
            self,
            "Download complete",
            f"Saved {count} file(s) to:\n{self._current_save_dir()}\n\n"
            "Licenses logged to _licenses.csv.\n"
            "Review each file for clinical appropriateness.",
        )

    def _on_download_error(self, msg: str) -> None:
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._on_log(f"\n❌ Error: {msg}")
        QMessageBox.critical(self, "Download failed", msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    win = PexelsDownloader()
    win.resize(780, 700)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
