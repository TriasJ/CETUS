"""Dev-only: screenshot the in-app Help viewer (TOC + a topic and the references)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from cravingcrave.ui.screens.help_dialog import HelpDialog  # noqa: E402
from cravingcrave.ui.theme import apply_theme  # noqa: E402

app = QApplication(sys.argv)
apply_theme(app)
out = ROOT / "docs" / "screenshots"

dlg = HelpDialog()
dlg.resize(940, 660)
dlg.show()
dlg.show_topic("vas")
app.processEvents()
dlg.grab().save(str(out / "16_help_vas.png"))
dlg.show_topic("references")
app.processEvents()
dlg.grab().save(str(out / "17_help_references.png"))
print("wrote help screenshots")
