"""Интерфейс publish: забирает dirty paths из data/tiles."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from activity_heatmap.config import Config


class PublishAdapter(ABC):
    @abstractmethod
    def publish(self, changed_paths: list[Path]) -> None:
        """Опубликовать/удалить изменённые тайлы. Пустой список — no-op."""


def get_publisher(config: Config) -> PublishAdapter:
    mode = config.publish_mode
    if mode == "github_pages":
        from activity_heatmap.publish.github_pages import GithubPagesPublisher

        return GithubPagesPublisher(config)
    if mode == "filesystem":
        from activity_heatmap.publish.filesystem import FilesystemPublisher

        return FilesystemPublisher(config)
    raise ValueError(f"Неизвестный PUBLISH_MODE={mode!r}")
