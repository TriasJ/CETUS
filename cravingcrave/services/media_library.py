"""Auto-discovery of cue media from the external ``media/`` folder.

Convention: ``media/{alcohol,cigarettes,meth,positive,sounds,neutral}/<file>``. The folder
name is the cue category; the file extension determines the media type. Clinicians
add personalized cues simply by dropping files into these folders — no rebuild.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ..domain.models import MediaItem, MediaType

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}

# Built-in cue/aux folders. Custom-substance folders (created at runtime) are
# discovered from disk by ``MediaLibrary.category_folders()`` and appended.
BUILTIN_CATEGORIES = ("alcohol", "cigarettes", "meth", "opioid", "positive", "sounds", "neutral")
# Back-compat alias (older callers import CATEGORIES).
CATEGORIES = BUILTIN_CATEGORIES


def media_type_for(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return MediaType.IMAGE.value
    if ext in VIDEO_EXTS:
        return MediaType.VIDEO.value
    if ext in AUDIO_EXTS:
        return MediaType.AUDIO.value
    return None


class MediaLibrary:
    def __init__(self, media_root: Path) -> None:
        self.media_root = Path(media_root)

    def category_folders(self) -> list[str]:
        """All cue folders present on disk: built-ins first (in canonical order),
        then any extra folders (custom substances) alphabetically."""
        present = set()
        if self.media_root.is_dir():
            present = {p.name for p in self.media_root.iterdir() if p.is_dir()}
        ordered = [c for c in BUILTIN_CATEGORIES if c in present]
        extra = sorted(present - set(BUILTIN_CATEGORIES))
        return ordered + extra

    def discover(self, categories: Iterable[str] | None = None) -> list[MediaItem]:
        if categories is None:
            categories = self.category_folders()
        items: list[MediaItem] = []
        for category in categories:
            folder = self.media_root / category
            if not folder.is_dir():
                continue
            for path in sorted(folder.iterdir()):
                if not path.is_file():
                    continue
                mtype = media_type_for(path)
                if mtype is None:
                    continue
                rel = f"{category}/{path.name}"
                items.append(
                    MediaItem(
                        path=rel,
                        absolute_path=str(path.resolve()),
                        substance=category,
                        media_type=mtype,
                        filename=path.name,
                    )
                )
        return items

    def by_category(self, category: str) -> list[MediaItem]:
        return self.discover([category])

    def absolute(self, relative_path: str) -> Path:
        return (self.media_root / relative_path).resolve()
