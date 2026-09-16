"""Simple PySide6 GUI for downloading YouTube videos into the media library.

Uses yt-dlp as the download backend.  Downloads are saved into media/<category>/
which is already git-ignored, so no .gitignore changes are needed.

    pip install yt-dlp PySide6
    python tools/youtube_gui.py

Optional: install ffmpeg and add it to PATH for higher resolutions (720p+)
and for re-encoding to the safe H.264+AAC playback profile.

IMPORTANT: Only import clips that are Creative-Commons licensed or that your
clinic has the right to use.  You are responsible for the licensing of
imported media.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Resolve project paths
# ---------------------------------------------------------------------------
TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent
MEDIA_ROOT = PROJECT_ROOT / "media"

CATEGORIES = [
    d.name
    for d in sorted(MEDIA_ROOT.iterdir())
    if d.is_dir() and not d.name.startswith(".")
] if MEDIA_ROOT.is_dir() else ["alcohol", "cigarettes", "cocaina", "meth", "neutral", "opioid", "positive", "sounds"]

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
# Resolution presets
# ---------------------------------------------------------------------------
# Each entry: (label, yt-dlp format WITH ffmpeg, yt-dlp format WITHOUT ffmpeg)
# Without ffmpeg yt-dlp can only download pre-muxed streams (video+audio in one
# file), which YouTube typically only offers at 360p (format 18).
RESOLUTIONS: list[tuple[str, str, str]] = [
    (
        "Best available",
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "best[ext=mp4]/best",
    ),
    (
        "1080p",
        "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best",
        "best[height<=1080][ext=mp4]/best[height<=1080]/best",
    ),
    (
        "720p",
        "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best",
        "best[height<=720][ext=mp4]/best[height<=720]/best",
    ),
    (
        "480p",
        "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best",
        "best[height<=480][ext=mp4]/best[height<=480]/best",
    ),
    (
        "360p",
        "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best",
        "best[height<=360][ext=mp4]/best[height<=360]/best",
    ),
]


def _ytdlp_cmd() -> list[str]:
    """Return the command prefix for yt-dlp (CLI binary or python -m).

    Automatically appends ``--js-runtimes <rt>`` when a supported runtime
    (bun, deno, node) is found on PATH — YouTube extraction requires one.
    """
    if shutil.which("yt-dlp"):
        base = ["yt-dlp"]
    else:
        try:
            import yt_dlp  # noqa: F401
            base = [sys.executable, "-m", "yt_dlp"]
        except ImportError:
            return []
    # Detect JS runtimes (yt-dlp needs one for YouTube)
    for rt in ("bun", "deno", "node"):
        if shutil.which(rt):
            base += ["--js-runtimes", rt]
            break
    return base


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


# ---------------------------------------------------------------------------
# Download worker (runs in a QThread)
# ---------------------------------------------------------------------------
class DownloadWorker(QThread):
    """Run yt-dlp (+ optional ffmpeg re-encode) in a background thread."""

    log = Signal(str)
    progress = Signal(int)           # 0-100
    finished_ok = Signal(str)        # final file path
    finished_err = Signal(str)       # error message

    def __init__(
        self,
        url: str,
        save_dir: Path,
        filename: str,
        fmt: str,
        reencode: bool = False,
        max_seconds: int = 0,
    ) -> None:
        super().__init__()
        self.url = url
        self.save_dir = save_dir
        self.filename = filename
        self.fmt = fmt
        self.reencode = reencode
        self.max_seconds = max_seconds
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    # -- main work --------------------------------------------------------

    def run(self) -> None:
        try:
            ytdlp = _ytdlp_cmd()
            if not ytdlp:
                self.finished_err.emit(
                    "yt-dlp not found.\nInstall it:  pip install yt-dlp"
                )
                return

            self.save_dir.mkdir(parents=True, exist_ok=True)
            final = self.save_dir / f"{self.filename}.mp4"

            if self.reencode and _has_ffmpeg():
                self._download_and_reencode(ytdlp, final)
            else:
                if self.reencode:
                    self.log.emit("⚠ ffmpeg not found — skipping re-encode.")
                self._download_direct(ytdlp, final)

            if self._cancelled:
                self.log.emit("Download cancelled.")
                return

            self.finished_ok.emit(str(final))

        except Exception as exc:
            self.finished_err.emit(str(exc))

    def _download_direct(self, ytdlp: list[str], final: Path) -> None:
        """Download merged mp4 directly."""
        self.log.emit(f"Downloading (format: {self.fmt})…")
        self.progress.emit(5)
        cmd = [
            *ytdlp,
            "-f", self.fmt,
            "--merge-output-format", "mp4",
            "--newline",
            "--no-mtime",
            "-o", str(final),
            self.url,
        ]
        self._run_with_progress(cmd, phase_start=5, phase_end=95)
        self.progress.emit(100)

    def _download_and_reencode(self, ytdlp: list[str], final: Path) -> None:
        """Download then re-encode to H.264+AAC (safe playback profile)."""
        with tempfile.TemporaryDirectory() as tmp:
            raw_template = str(Path(tmp) / "raw.%(ext)s")

            self.log.emit(f"Downloading (format: {self.fmt})…")
            self.progress.emit(5)
            cmd = [
                *ytdlp,
                "-f", self.fmt,
                "--merge-output-format", "mp4",
                "--newline",
                "--no-mtime",
                "-o", raw_template,
                self.url,
            ]
            self._run_with_progress(cmd, phase_start=5, phase_end=50)

            if self._cancelled:
                return

            downloaded = next(Path(tmp).glob("raw.*"), None)
            if downloaded is None:
                self.finished_err.emit("yt-dlp succeeded but no output file found.")
                return

            self.log.emit("Re-encoding to H.264 + AAC…")
            self.progress.emit(55)
            cmd = ["ffmpeg", "-y", "-i", str(downloaded)]
            if self.max_seconds > 0:
                cmd += ["-t", str(self.max_seconds)]
            cmd += [
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-movflags", "+faststart",
                str(final),
            ]
            self._run_with_progress(cmd, phase_start=55, phase_end=95)
            self.progress.emit(100)

    def _run_with_progress(
        self, cmd: list[str], phase_start: int, phase_end: int,
    ) -> None:
        """Run a subprocess, relay output, and estimate progress."""
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=(
                subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            ),
        )
        pct_range = phase_end - phase_start
        try:
            for line in proc.stdout:
                if self._cancelled:
                    proc.terminate()
                    return
                line = line.rstrip()
                if not line:
                    continue
                self.log.emit(line)
                m = re.search(r"\[download\]\s+([\d.]+)%", line)
                if m:
                    dl_pct = min(float(m.group(1)), 100.0)
                    self.progress.emit(
                        phase_start + int(dl_pct / 100 * pct_range)
                    )
        finally:
            proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(
                f"Command failed (exit {proc.returncode}): {' '.join(cmd[:3])}…\n"
                "Check the log above for details."
            )


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class YouTubeDownloader(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CETUS — YouTube Media Importer")
        self.setMinimumWidth(620)
        self.worker: DownloadWorker | None = None
        self._custom_folder: Path | None = None
        self._ffmpeg = _has_ffmpeg()
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        # Header
        title = QLabel("YouTube Media Importer")
        title.setObjectName("H2")
        root.addWidget(title)

        subtitle = QLabel(
            "Download a YouTube video into the media library.  "
            "Only import clips that are Creative-Commons licensed or "
            "that your clinic has the right to use."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # ffmpeg warning banner
        if not self._ffmpeg:
            banner = QLabel(
                "⚠ ffmpeg not found on PATH — merging and re-encoding are "
                "disabled.  Without ffmpeg only pre-muxed streams are "
                "available (usually ≤360p).  Install ffmpeg for full "
                "resolution support."
            )
            banner.setObjectName("Warning")
            banner.setWordWrap(True)
            root.addWidget(banner)

        # URL
        root.addWidget(QLabel("YouTube URL"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "https://www.youtube.com/watch?v=… or https://youtu.be/…"
        )
        root.addWidget(self.url_edit)

        # Category + Resolution + Filename row
        row = QHBoxLayout()

        col_cat = QVBoxLayout()
        col_cat.addWidget(QLabel("Category"))
        self.category_combo = QComboBox()
        self.category_combo.addItems(CATEGORIES)
        col_cat.addWidget(self.category_combo)
        row.addLayout(col_cat)

        col_res = QVBoxLayout()
        col_res.addWidget(QLabel("Resolution"))
        self.resolution_combo = QComboBox()
        for label, _, _ in RESOLUTIONS:
            self.resolution_combo.addItem(label)
        col_res.addWidget(self.resolution_combo)
        row.addLayout(col_res)

        col_name = QVBoxLayout()
        col_name.addWidget(QLabel("Filename (no extension)"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. bar_scene_01")
        col_name.addWidget(self.name_edit)
        row.addLayout(col_name, stretch=1)

        root.addLayout(row)

        # Save-to folder
        root.addWidget(QLabel("Save to folder"))
        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self._update_folder_display()
        folder_row.addWidget(self.folder_edit, stretch=1)
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(browse_btn)
        root.addLayout(folder_row)

        self.category_combo.currentTextChanged.connect(
            lambda _: self._update_folder_display()
        )

        # Re-encode checkbox
        self.reencode_cb = QCheckBox("Re-encode to H.264 + AAC (safe playback)")
        self.reencode_cb.setChecked(self._ffmpeg)
        self.reencode_cb.setEnabled(self._ffmpeg)
        if not self._ffmpeg:
            self.reencode_cb.setToolTip("Requires ffmpeg on PATH")
        root.addWidget(self.reencode_cb)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.download_btn = QPushButton("  Download  ")
        self.download_btn.setObjectName("Primary")
        self.download_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self.download_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("Danger")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_download)
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
        self.log_view.setMaximumHeight(200)
        self.log_view.setPlaceholderText("Download log will appear here…")
        root.addWidget(self.log_view, stretch=1)

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
            QLabel#Warning {{
                background-color: #fff3cd;
                color: #856404;
                border: 1px solid #ffc107;
                border-radius: 7px;
                padding: 8px 12px;
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
                padding: 9px 16px;
                min-height: 22px;
            }}
            QPushButton:hover {{ background-color: #eef2f5; }}
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
            QCheckBox {{
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid #c5ced6;
                border-radius: 4px;
                background-color: {SURFACE};
            }}
            QCheckBox::indicator:checked {{
                background-color: {PRIMARY};
                border-color: {PRIMARY};
            }}
            QCheckBox:disabled {{
                color: {MUTED};
            }}
            QProgressBar {{
                background-color: #e1e6eb;
                border: none;
                border-radius: 6px;
                height: 14px;
                text-align: center;
                font-size: 11px;
            }}
            QProgressBar::chunk {{
                background-color: {PRIMARY};
                border-radius: 6px;
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

    def _update_folder_display(self) -> None:
        self.folder_edit.setText(str(self._current_save_dir()))

    def _browse_folder(self) -> None:
        start = str(self._current_save_dir())
        folder = QFileDialog.getExistingDirectory(
            self, "Choose save folder", start,
        )
        if folder:
            self._custom_folder = Path(folder)
            self._update_folder_display()

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        name = re.sub(r'[<>:"/\\|?*]', "_", name.strip())
        name = re.sub(r"\s+", "_", name)
        name = name.strip("_.")
        return name or "video"

    def _selected_format(self) -> str:
        """Return the yt-dlp format string for the chosen resolution."""
        idx = self.resolution_combo.currentIndex()
        _, fmt_ffmpeg, fmt_no_ffmpeg = RESOLUTIONS[idx]
        return fmt_ffmpeg if self._ffmpeg else fmt_no_ffmpeg

    # -- download ----------------------------------------------------------

    def _start_download(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Paste a YouTube URL first.")
            return

        raw_name = self.name_edit.text().strip()
        filename = self._sanitize_filename(raw_name) if raw_name else ""
        if not filename:
            QMessageBox.warning(
                self, "Missing filename", "Enter a filename for the video.",
            )
            return

        save_dir = self._current_save_dir()
        target = save_dir / f"{filename}.mp4"
        if target.exists():
            reply = QMessageBox.question(
                self,
                "File exists",
                f"{target.name} already exists.\nOverwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        fmt = self._selected_format()
        reencode = self.reencode_cb.isChecked()

        self.log_view.clear()
        self.progress_bar.setValue(0)
        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        self.worker = DownloadWorker(
            url=url,
            save_dir=save_dir,
            filename=filename,
            fmt=fmt,
            reencode=reencode,
        )
        self.worker.log.connect(self._on_log)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.finished_err.connect(self._on_error)
        self.worker.start()

    def _cancel_download(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self._on_log("Cancelling…")

    def _on_log(self, text: str) -> None:
        self.log_view.append(text)
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_done(self, path: str) -> None:
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setValue(100)
        self._on_log(f"\n✅ Saved to {path}")
        QMessageBox.information(
            self,
            "Download complete",
            f"Video saved to:\n{path}\n\n"
            "Confirm the clip is CC-licensed or cleared for clinical use.",
        )

    def _on_error(self, msg: str) -> None:
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
    win = YouTubeDownloader()
    win.resize(660, 580)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
