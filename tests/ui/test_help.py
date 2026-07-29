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

    # The shortcuts topic lists the new intensity / loop / fullscreen bindings.
    sc = next(s for s in sections if s["id"] == "shortcuts")["html"]
    for token in ("T</b>", "D</b>", "O</b>", "M</b>", "R</b>", "L</b>", "F11</b>",
                  "Tamaño", "Desenfoque", "Oscurecer", "bucle"):
        assert token in sc, f"missing shortcut token: {token}"

    # The mechanisms topic exists and cites the behavioral-science evidence.
    mech = next(s for s in sections if s["id"] == "mecanismos")["html"]
    assert "Pavloviano" in mech or "pavloviano" in mech
    assert "Carter" in mech and "Kiyak" in mech and "extinción" in mech.lower()

    # 0.4.0 features are documented: keyboard-only mode, auto-scroll, coping export,
    # and where data is stored.
    assert "solo teclado" in sc.lower()                       # accessibility in shortcuts
    graded = next(s for s in sections if s["id"] == "graded")["html"]
    assert "autom" in graded.lower()                          # auto-scroll
    rep = next(s for s in sections if s["id"] == "report_metrics")["html"]
    assert "afrontamiento" in rep.lower()                     # coping export
    mgmt = next(s for s in sections if s["id"] == "management")["html"]
    assert "%APPDATA%" in mgmt and "portable" in mgmt.lower()  # data location


def test_help_has_session_workflow_topic():
    # 0.5.0: an end-to-end session-workflow narrative in both locales.
    es = {s["id"]: s["html"] for s in load_help("es")["sections"]}
    assert "workflow" in es
    wf_es = es["workflow"]
    assert "línea base" in wf_es.lower() and "habituación" in wf_es.lower()
    assert "afrontamiento" in wf_es.lower() and "poco a poco" in wf_es.lower()

    en = {s["id"]: s["html"] for s in load_help("en")["sections"]}
    assert "workflow" in en
    wf_en = en["workflow"]
    assert "baseline" in wf_en.lower() and "habituation" in wf_en.lower()
    assert "coping" in wf_en.lower() and "little by little" in wf_en.lower()


def test_help_english_documents_new_features():
    data = load_help("en")
    sections = {s["id"]: s["html"] for s in data["sections"]}
    assert "keyboard-only mode" in sections["shortcuts"].lower()
    assert "automatic advance" in sections["graded"].lower()
    assert "coping" in sections["report_metrics"].lower()
    assert "%APPDATA%" in sections["management"]
    # Numbers-in-fullscreen + keys 4/5 documented in shortcuts.
    assert "4/5" in sections["shortcuts"] or "4 / 5" in sections["shortcuts"]


def test_help_dialog_renders_and_navigates(qtbot):
    dlg = HelpDialog()
    qtbot.addWidget(dlg)
    assert dlg.toc.count() == len(dlg._sections)
    dlg.show_topic("uscs")
    assert dlg._sections[dlg.toc.currentRow()]["id"] == "uscs"
    assert dlg.browser.toPlainText().strip() != ""
