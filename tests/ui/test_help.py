"""In-app help/manual: content loads, has citations, and the dialog renders it."""

from cravingcrave.services.help import load_help
from cravingcrave.ui.screens.help_dialog import HelpDialog


def test_help_content_loads_with_citations():
    data = load_help("es")
    sections = data["sections"]
    assert len(sections) >= 10
    for s in sections:
        assert s.get("id") and s.get("title") and s.get("html")
    ids = {s["id"] for s in sections}
    assert {"overview", "cet", "vas", "habituacion", "uscs", "safety", "references"} <= ids
    refs = next(s for s in sections if s["id"] == "references")["html"]
    assert "Mellentin" in refs and "PMC10980682" in refs and "Monti" in refs

    # The new habituacion section explains the precise rule and parameters.
    hab = next(s for s in sections if s["id"] == "habituacion")["html"]
    assert "consecutivas" in hab and "Umbral" in hab and "Pendiente" in hab
    assert "Ajustes" in hab and "PMC10980682" in hab

    # The shortcuts topic lists the new intensity / loop bindings.
    sc = next(s for s in sections if s["id"] == "shortcuts")["html"]
    for token in ("T</b>", "D</b>", "O</b>", "M</b>", "R</b>", "L</b>", "Tamaño", "Desenfoque", "Oscurecer", "bucle"):
        assert token in sc, f"missing shortcut token: {token}"


def test_help_dialog_renders_and_navigates(qtbot):
    dlg = HelpDialog()
    qtbot.addWidget(dlg)
    assert dlg.toc.count() == len(dlg._sections)
    dlg.show_topic("uscs")
    assert dlg._sections[dlg.toc.currentRow()]["id"] == "uscs"
    assert dlg.browser.toPlainText().strip() != ""
