"""Ensure the project root is importable so `import cravingcrave` works under pytest,
and force Qt's offscreen platform so GUI tests run headlessly in CI."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
