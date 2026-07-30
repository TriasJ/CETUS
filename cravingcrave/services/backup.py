"""Backup & restore of the whole CETUS dataset (SQLite DB + media folder).

Qt-free so it is unit-testable. A backup is a ``.zip`` containing:
  * ``cravingcrave.db`` — a consistent snapshot taken with the sqlite3 online backup API
    (never a raw copy of the possibly-in-use file),
  * ``media/**`` — the cue/media tree,
  * ``manifest.json`` — marker, app + schema version, timestamp and counts.

Restore first writes a **pre-restore safety zip** of the current data, then replaces the DB and
media from the backup. The caller MUST close the live DB connection before restoring and prompt
for a restart afterwards — restore never hot-swaps the running connection.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from ..data.migrations import CURRENT_VERSION

MARKER = "cetus-backup"
MANIFEST_NAME = "manifest.json"
DB_ARCNAME = "cravingcrave.db"
MEDIA_PREFIX = "media/"


def _snapshot_db(db_path: Path, out_file: Path) -> None:
    """Consistent DB copy via the online backup API (safe while the app holds the DB open)."""
    src = sqlite3.connect(str(db_path))
    try:
        dst = sqlite3.connect(str(out_file))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def create_backup(db_path, media_root, dest_zip, app_version: str,
                  created_at: str, counts: dict | None = None) -> dict:
    """Write a backup zip and return its manifest. ``created_at`` is supplied by the caller."""
    db_path, media_root, dest_zip = Path(db_path), Path(media_root), Path(dest_zip)
    manifest = {
        "marker": MARKER,
        "app_version": app_version,
        "schema_version": CURRENT_VERSION,
        "created_at": created_at,
        "counts": dict(counts or {}),
    }
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / DB_ARCNAME
        if db_path.exists():
            _snapshot_db(db_path, snap)
        media_files = 0
        with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as z:
            if snap.exists():
                z.write(snap, DB_ARCNAME)
            if media_root.exists():
                for p in sorted(media_root.rglob("*")):
                    if p.is_file():
                        z.write(p, MEDIA_PREFIX + p.relative_to(media_root).as_posix())
                        media_files += 1
            manifest["media_file_count"] = media_files
            z.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))
    return manifest


def read_manifest(zip_path) -> dict | None:
    """Return the manifest if ``zip_path`` is a valid CETUS backup, else None."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            if MANIFEST_NAME not in z.namelist():
                return None
            data = json.loads(z.read(MANIFEST_NAME).decode("utf-8"))
    except (zipfile.BadZipFile, OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("marker") == MARKER else None


def _safe_media_target(media_root: Path, arcname: str) -> Path | None:
    """Resolve a ``media/…`` archive entry under media_root, rejecting path traversal."""
    rel = arcname[len(MEDIA_PREFIX):]
    target = (media_root / rel).resolve()
    root = media_root.resolve()
    if target == root or root not in target.parents:
        return None
    return target


def restore_backup(db_path, media_root, zip_path, pre_restore_zip,
                   app_version: str, created_at: str) -> dict:
    """Replace the DB + media from a backup, after writing a pre-restore safety zip.

    The caller must have closed the live DB connection first. Raises ValueError on a bad archive.
    """
    manifest = read_manifest(zip_path)
    if manifest is None:
        raise ValueError("Not a CETUS backup archive.")
    if int(manifest.get("schema_version", 0)) > CURRENT_VERSION:
        raise ValueError("Backup is from a newer version of CETUS.")
    db_path, media_root = Path(db_path), Path(media_root)

    # Safety net: snapshot the current data before overwriting it.
    create_backup(db_path, media_root, pre_restore_zip, app_version, created_at, {})

    if media_root.exists():
        shutil.rmtree(media_root)
    media_root.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        if DB_ARCNAME in names:
            with z.open(DB_ARCNAME) as src, open(db_path, "wb") as out:
                shutil.copyfileobj(src, out)
        for name in names:
            if not name.startswith(MEDIA_PREFIX) or name.endswith("/"):
                continue
            target = _safe_media_target(media_root, name)
            if target is None:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(name) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
    return manifest
