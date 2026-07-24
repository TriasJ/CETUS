"""Application logging configuration.

CETUS is a local-only clinical tool, so logs stay on the machine next to the data
folder. A rotating file handler keeps a bounded history for troubleshooting; a
console handler helps during development. Call :func:`configure_logging` once at
startup (from ``app.main``), after the data directory is known.

Logs never contain patient identifiers by convention — log codes/ids and error
types, not names or free-text notes.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def configure_logging(data_dir: Path, level: int = logging.INFO) -> Path | None:
    """Set up root logging to ``data_dir/cetus.log`` (rotating) + console.

    Idempotent: safe to call more than once. Returns the log file path, or None if
    the file handler could not be created (logging then falls back to console only).
    """
    global _CONFIGURED
    if _CONFIGURED:
        return None
    _CONFIGURED = True

    root = logging.getLogger()
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    log_path: Path | None = None
    try:
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        log_path = Path(data_dir) / "cetus.log"
        file_handler = RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError:
        # Read-only/locked data dir — keep console logging, don't crash startup.
        logging.getLogger(__name__).warning("File logging unavailable; console only.")
        log_path = None

    logging.getLogger(__name__).info("Logging initialised.")
    return log_path
