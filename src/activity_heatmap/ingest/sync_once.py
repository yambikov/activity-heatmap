"""Общий entry для одноразового sync (CLI и старт agent)."""

from __future__ import annotations

from pathlib import Path

from activity_heatmap.ingest.base import IngestAdapter


def run_sync_once(ingest: IngestAdapter) -> list[Path]:
    return ingest.sync_once()
