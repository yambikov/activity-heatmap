"""Publish в S3/R2. Опционально, этап 3+."""

from __future__ import annotations

from pathlib import Path

from activity_heatmap.config import Config
from activity_heatmap.publish.base import PublishAdapter


class S3Publisher(PublishAdapter):
    def __init__(self, config: Config) -> None:
        self.config = config

    def publish(self, changed_paths: list[Path]) -> None:
        raise NotImplementedError("S3Publisher: этап 3+")
