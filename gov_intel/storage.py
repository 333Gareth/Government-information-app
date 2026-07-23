"""Atomic, logged JSON persistence helpers.

The original app wrote JSON with a plain ``open(path, "w")``, which
means a crash or power loss mid-write leaves a truncated/corrupt file.
``save_json`` here writes to a temp file in the same directory and
atomically renames it into place, so a reader never observes a partial
write.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_json(path: Path, default: Any) -> Any:
    """Load JSON from ``path``, returning ``default`` if missing/corrupt.

    Errors are logged rather than silently swallowed, so a corrupt file
    is visible in the logs instead of just quietly resetting state.
    """
    path = Path(path)
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load JSON from %s (%s); using default.", path, exc)
        return default


def save_json(path: Path, data: Any) -> None:
    """Write ``data`` as JSON to ``path`` atomically.

    Writes to a temp file in the same directory first, then uses
    ``os.replace`` (atomic on POSIX and Windows) to move it into place.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_name, path)
    except Exception:
        # Clean up the temp file if the write/replace failed.
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        logger.exception("Failed to save JSON to %s", path)
        raise
