"""Стабильный ключ активности = content hash файла."""

from __future__ import annotations

import hashlib
from pathlib import Path


def activity_id_for_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:40]
