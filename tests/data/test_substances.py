"""Custom-substances service: slugging, add/hide, built-ins locked, JSON round-trip."""

from cravingcrave.data.database import Database
from cravingcrave.data.repositories import Repositories
from cravingcrave.services import substances as subs


def _settings():
    return Repositories(Database(":memory:")).settings


def test_slugify():
    assert subs.slugify("Cocaína") == "cocaina"
    assert subs.slugify("  Opioides / Heroína ") == "opioides-heroina"
    assert subs.slugify("!!!") == ""


def test_builtins_present_and_locked():
    s = _settings()
    keys = [k for k, _ in subs.available_substances(s)]
    assert keys[:3] == ["alcohol", "cigarettes", "meth"]
    # Adding a slug that collides with a built-in is rejected.
    assert subs.add_custom(s, "Alcohol") is None


def test_add_and_hide_roundtrip():
    s = _settings()
    key = subs.add_custom(s, "Cocaína")
    assert key == "cocaina"
    assert ("cocaina", "Cocaína") in subs.custom_substances(s)
    assert subs.display_name(s, "cocaina") == "Cocaína"
    # available_substances now includes it after the built-ins.
    assert [k for k, _ in subs.available_substances(s)][-1] == "cocaina"
    # Duplicate add rejected.
    assert subs.add_custom(s, "Cocaína") is None
    # Hide removes from the list but display_name still resolves to verbatim key.
    subs.hide_custom(s, "cocaina")
    assert subs.custom_substances(s) == []


def test_display_name_fallbacks():
    s = _settings()
    assert subs.display_name(s, "meth")  # built-in via i18n, non-empty
    assert subs.display_name(s, "legacy-unknown") == "legacy-unknown"  # never blank


def test_empty_label_rejected():
    s = _settings()
    assert subs.add_custom(s, "   ") is None
    assert subs.add_custom(s, "###") is None
