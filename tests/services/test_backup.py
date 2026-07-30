"""Backup/restore service: zip contents, manifest, round-trip, and guards."""

import json
import zipfile
from pathlib import Path

from cravingcrave.data.database import Database
from cravingcrave.data.repositories import Repositories
from cravingcrave.domain.models import Patient
from cravingcrave.services import backup

TS = "2026-07-30T00:00:00+00:00"


def _seed(db_path: Path, media_root: Path, code: str) -> None:
    """Create a DB with one patient and one media file, then close the connection."""
    db = Database(db_path)
    Repositories(db).patients.create(Patient(code=code, primary_substance="meth"))
    db.close()
    f = media_root / "meth" / f"{code}.png"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"img")


def test_create_backup_zip_contents_and_manifest(tmp_path):
    db_path = tmp_path / "data" / "cravingcrave.db"
    media = tmp_path / "media"
    _seed(db_path, media, "PT01")
    dest = tmp_path / "backup.zip"

    manifest = backup.create_backup(db_path, media, dest, "0.6.0", TS, {"patients": 1})

    assert dest.exists()
    with zipfile.ZipFile(dest) as z:
        names = z.namelist()
        assert backup.DB_ARCNAME in names
        assert backup.MANIFEST_NAME in names
        assert any(n.startswith("media/") and n.endswith("PT01.png") for n in names)
        m = json.loads(z.read(backup.MANIFEST_NAME))
    assert m["marker"] == "cetus-backup"
    assert m["counts"]["patients"] == 1
    assert m["media_file_count"] == 1
    assert manifest["schema_version"] == m["schema_version"]


def test_restore_round_trip_and_pre_restore_safety_zip(tmp_path):
    db_path = tmp_path / "data" / "cravingcrave.db"
    media = tmp_path / "media"
    _seed(db_path, media, "PT01")

    good = tmp_path / "good.zip"
    backup.create_backup(db_path, media, good, "0.6.0", TS, {})

    # Mutate after the backup: add a second patient + media file.
    db = Database(db_path)
    Repositories(db).patients.create(Patient(code="PT02", primary_substance="meth"))
    db.close()
    (media / "meth" / "PT02.png").write_bytes(b"img2")

    pre = tmp_path / "pre.zip"
    backup.restore_backup(db_path, media, good, pre, "0.6.0", TS)

    # Restored DB has only the first patient; the second media file is gone.
    db = Database(db_path)
    assert Repositories(db).patients.count() == 1
    db.close()
    assert (media / "meth" / "PT01.png").exists()
    assert not (media / "meth" / "PT02.png").exists()
    # The pre-restore safety zip captured the mutated state (2 patients).
    assert backup.read_manifest(pre) is not None
    with zipfile.ZipFile(pre) as z:
        assert any(n.endswith("PT02.png") for n in z.namelist())


def test_read_manifest_rejects_non_cetus_zip(tmp_path):
    junk = tmp_path / "junk.zip"
    with zipfile.ZipFile(junk, "w") as z:
        z.writestr("hello.txt", "not a backup")
    assert backup.read_manifest(junk) is None


def test_restore_refuses_newer_schema(tmp_path):
    db_path = tmp_path / "data" / "cravingcrave.db"
    media = tmp_path / "media"
    _seed(db_path, media, "PT01")
    future = tmp_path / "future.zip"
    with zipfile.ZipFile(future, "w") as z:
        z.writestr(backup.MANIFEST_NAME,
                   json.dumps({"marker": "cetus-backup", "schema_version": 999}))
    try:
        backup.restore_backup(db_path, media, future, tmp_path / "pre.zip", "0.6.0", TS)
        raised = False
    except ValueError:
        raised = True
    assert raised
