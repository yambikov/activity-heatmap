"""Интерфейс ingest: вызывает только core add/remove/rebuild."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class IngestAdapter(ABC):
    @abstractmethod
    def sync_once(self) -> list[Path]:
        """Сверить источник с activities → add/remove → список dirty tiles."""

    @abstractmethod
    def run_forever(self) -> None:
        """Долгоживущий режим (FS watch или webhook listener)."""
