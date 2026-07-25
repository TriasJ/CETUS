"""External data/media path resolution across dev / portable / installed builds."""

from pathlib import Path

from cravingcrave import paths


def test_dev_uses_project_root(monkeypatch):
    monkeypatch.setattr(paths, "is_frozen", lambda: False)
    # Project root = parent of the package dir.
    assert paths.app_base_dir() == paths._PACKAGE_DIR.parent
    assert paths.data_dir().name == "data"
    assert paths.db_path().name == "cravingcrave.db"


def test_frozen_portable_marker_uses_next_to_exe(monkeypatch, tmp_path):
    exe = tmp_path / "CETUS.exe"
    exe.write_text("x")
    (tmp_path / "portable.txt").write_text("")
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(paths.sys, "executable", str(exe))
    assert paths.app_base_dir() == tmp_path


def test_frozen_existing_data_folder_uses_next_to_exe(monkeypatch, tmp_path):
    exe = tmp_path / "CETUS.exe"
    exe.write_text("x")
    (tmp_path / "data").mkdir()   # existing deployment
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(paths.sys, "executable", str(exe))
    assert paths.app_base_dir() == tmp_path


def test_frozen_installed_uses_per_os_user_dir(monkeypatch, tmp_path):
    # Frozen, no portable marker and no data/ beside exe -> per-OS user dir.
    exe = tmp_path / "app" / "CETUS.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("x")
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(paths.sys, "executable", str(exe))
    fake_user = tmp_path / "userdata"
    monkeypatch.setattr(paths, "user_data_root", lambda: fake_user)
    assert paths.app_base_dir() == fake_user


def test_user_data_root_per_platform(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setattr(paths.os, "environ", {"APPDATA": str(tmp_path / "roaming")})
    assert paths.user_data_root() == tmp_path / "roaming" / "CETUS"

    monkeypatch.setattr(paths.sys, "platform", "darwin")
    monkeypatch.setattr(paths.os, "environ", {})
    assert paths.user_data_root() == home / "Library" / "Application Support" / "CETUS"

    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setattr(paths.os, "environ", {})
    assert paths.user_data_root() == home / ".local" / "share" / "CETUS"

    monkeypatch.setattr(paths.os, "environ", {"XDG_DATA_HOME": str(tmp_path / "xdg")})
    assert paths.user_data_root() == tmp_path / "xdg" / "CETUS"
