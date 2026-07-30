"""0.6.4 themes: registry, per-theme stylesheet application, persistence."""

from cravingcrave.config import AppConfig
from cravingcrave.ui import theme
from cravingcrave.ui.context import AppContext


def test_available_themes():
    t = theme.available_themes()
    assert t[0] == "light"                       # default first
    assert set(t) >= {"light", "dark", "high_contrast", "impaired", "classic"}


def test_apply_each_theme_sets_a_stylesheet(qapp):
    base_len = None
    for name in theme.available_themes():
        theme.apply_theme(qapp, name)
        css = qapp.styleSheet()
        assert css.strip() != ""
        if name == "light":
            base_len = len(css)
    # A non-default theme appends its override marker on top of the base.
    theme.apply_theme(qapp, "dark")
    assert "theme: dark" in qapp.styleSheet()
    assert len(qapp.styleSheet()) > (base_len or 0)
    theme.apply_theme(qapp, "light")             # restore for other tests


def test_theme_persists_and_reloads(tmp_path):
    kw = dict(data_dir=tmp_path / "data", media_root=tmp_path / "media",
              db_path=tmp_path / "data" / "cc.db")
    ctx = AppContext.create(AppConfig(**kw))
    assert ctx.config.theme == "light"           # default
    ctx.repos.settings.set("theme", "high_contrast")
    cfg2 = AppConfig(**kw)
    AppContext.create(cfg2)                       # re-reads settings into config
    assert cfg2.theme == "high_contrast"
