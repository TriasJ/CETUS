"""Localization: locale-file key parity, help-topic parity, auto-discovery, and the
live language switcher (Settings + login) that re-renders in the new language."""

import json

import pytest

from cravingcrave import paths
from cravingcrave.config import AppConfig
from cravingcrave.services import i18n
from cravingcrave.services.help import load_help
from cravingcrave.services.i18n import DEFAULT_LOCALE, available_locales, current_locale
from cravingcrave.ui.context import AppContext
from cravingcrave.ui.main_window import MainWindow


def _locale_files():
    return sorted(paths.resource_path("i18n").glob("*.json"))


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------- key parity across every shipped locale --------------------------

def test_default_locale_ships():
    assert (paths.resource_path("i18n") / f"{DEFAULT_LOCALE}.json").is_file()


def test_every_locale_has_the_same_keys_as_default():
    """Adding a language must be drop-in: each locale JSON must define exactly the
    same keys as the default (es), so no UI string silently falls back to its key."""
    ref_path = paths.resource_path("i18n", f"{DEFAULT_LOCALE}.json")
    ref = set(_load(ref_path))
    assert "_language.name" in ref and "app.language" in ref
    for path in _locale_files():
        keys = set(_load(path))
        missing = ref - keys
        extra = keys - ref
        assert not missing, f"{path.name} missing keys: {sorted(missing)[:10]}"
        assert not extra, f"{path.name} has extra keys: {sorted(extra)[:10]}"


def test_language_native_name_present_in_each_locale():
    for path in _locale_files():
        data = _load(path)
        assert data.get("_language.name"), f"{path.name} lacks _language.name"


# ---------- auto-discovery --------------------------------------------------

def test_available_locales_discovers_es_and_en():
    codes = {code for code, _name in available_locales()}
    assert {"es", "en"} <= codes


def test_available_locales_lists_default_first_with_native_names():
    locales = available_locales()
    assert locales[0][0] == DEFAULT_LOCALE
    names = dict(locales)
    assert names["es"] == "Español"
    assert names["en"] == "English"


# ---------- help-topic parity -----------------------------------------------

def test_help_topics_match_across_locales():
    """Every translated manual must keep the same topic ids/order as the default so
    contextual `show_topic(id)` jumps work regardless of language."""
    ref_ids = [s["id"] for s in load_help(DEFAULT_LOCALE)["sections"]]
    for path in _locale_files():
        code = path.stem
        ids = [s["id"] for s in load_help(code)["sections"]]
        assert ids == ref_ids, f"help/{code}.json topic ids/order differ"


def test_help_falls_back_to_default_for_unknown_locale():
    # A locale with no translated manual still yields the default (non-empty) help.
    data = load_help("zz-nonexistent")
    assert data["sections"]


# ---------- the live switcher -----------------------------------------------

@pytest.fixture
def ctx(tmp_path, qapp):
    cfg = AppConfig(data_dir=tmp_path / "data", media_root=tmp_path / "media",
                    db_path=tmp_path / "data" / "cc.db")
    return AppContext.create(cfg)


@pytest.fixture(autouse=True)
def _restore_locale():
    original = current_locale()
    yield
    i18n.set_locale(original)


def test_change_language_persists_and_switches(ctx, qtbot):
    i18n.set_locale("es")
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    window.change_language("en")
    assert current_locale() == "en"
    assert ctx.config.locale == "en"
    assert ctx.repos.settings.get("locale") == "en"          # persisted for next launch
    assert window.windowTitle() == i18n.tr("app.title")


def test_change_language_noop_for_same_locale(ctx, qtbot):
    i18n.set_locale("es")
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    called = []
    window.change_language("es", redisplay=lambda: called.append(1))
    assert called == []                                       # no redundant re-render
    assert current_locale() == "es"


def test_settings_language_combo_re_renders(ctx, qtbot):
    from cravingcrave.ui.screens.settings_screen import SettingsScreen
    i18n.set_locale("es")
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    window.show()
    screen = SettingsScreen(window, ctx)
    qtbot.addWidget(screen)
    idx = screen.lang_combo.findData("en")
    assert idx >= 0
    screen.lang_combo.setCurrentIndex(idx)
    screen._on_language_changed(idx)
    assert current_locale() == "en"
    assert ctx.repos.settings.get("locale") == "en"


def test_login_language_combo_present_and_switches(ctx, qtbot):
    from cravingcrave.ui.screens.login_screen import LoginScreen
    i18n.set_locale("es")
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    window.show()
    screen = LoginScreen(window, ctx)
    qtbot.addWidget(screen)
    idx = screen.lang_combo.findData("en")
    assert idx >= 0
    screen._on_language_changed(idx)
    assert current_locale() == "en"


def test_saved_locale_is_applied_when_context_loads(ctx):
    # Persisting a locale then re-reading settings into a config makes it win over the
    # bootstrap default (this is what app.main() relies on).
    ctx.repos.settings.set("locale", "en")
    cfg = AppConfig(data_dir=ctx.config.data_dir, media_root=ctx.config.media_root,
                    db_path=ctx.config.db_path)
    AppContext.create(cfg)
    assert cfg.locale == "en"
