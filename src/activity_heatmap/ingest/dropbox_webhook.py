"""Ingest для VDS: Dropbox webhook. Вне скоупа v1 на ПК."""

from __future__ import annotations

from pathlib import Path

from activity_heatmap.ingest.base import IngestAdapter


class DropboxWebhookIngest(IngestAdapter):
    def sync_once(self) -> list[Path]:
        raise NotImplementedError("dropbox_webhook: этап 3 (VDS)")

    def run_forever(self) -> None:
        raise NotImplementedError("dropbox_webhook: этап 3 (VDS)")
