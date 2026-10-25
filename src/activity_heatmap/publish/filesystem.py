"""Publish на VDS: тайлы уже в data/tiles, раздаёт nginx/Caddy. По сути no-op."""

from __future__ import annotations

import logging
from pathlib import Path

from activity_heatmap.config import Config
from activity_heatmap.publish.base import PublishAdapter

log = logging.getLogger(__name__)


class FilesystemPublisher(PublishAdapter):
    def __init__(self, config: Config) -> None:
        self.config = config

    def publish(self, changed_paths: list[Path]) -> None:
        log.info(
            "filesystem publish: %d путей уже в %s",
            len(changed_paths),
            self.config.tiles_dir,
        )
