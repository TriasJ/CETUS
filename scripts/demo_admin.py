"""Dev-only: screenshot the admin recovery dialog (key page + recovery page)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from cravingcrave.config import AppConfig  # noqa: E402
from cravingcrave.ui.context import AppContext  # noqa: E402
from cravingcrave.ui.screens.admin_dialog import AdminDialog  # noqa: E402
from cravingcrave.ui.theme import apply_theme  # noqa: E402

app = QApplication(sys.argv)
apply_theme(app)
tmp = Path(tempfile.mkdtemp())
cfg = AppConfig(data_dir=tmp / "data", media_root=tmp / "media", db_path=tmp / "data" / "cc.db")
ctx = AppContext.create(cfg)
ctx.auth.register("AlanH", "Dr. Alan Hinojosa", "x")
ctx.auth.register("draruiz", "Dra. Ruiz", "y")

out = ROOT / "docs" / "screenshots"
dlg = AdminDialog(ctx)
dlg.resize(480, 360)
dlg.show()
app.processEvents()
dlg.grab().save(str(out / "14_admin_key.png"))

dlg.key_input.setText("cetus-admin")
dlg._check_key()
app.processEvents()
dlg.grab().save(str(out / "15_admin_recovery.png"))
print("wrote admin dialog screenshots")
