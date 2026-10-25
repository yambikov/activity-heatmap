"""Publish v1: git add/commit/push dirty tiles в Pages."""

from __future__ import annotations

import logging
from pathlib import Path

from activity_heatmap.config import Config
from activity_heatmap.publish.base import PublishAdapter

log = logging.getLogger(__name__)


class GithubPagesPublisher(PublishAdapter):
    def __init__(self, config: Config) -> None:
        self.config = config

    def publish(self, changed_paths: list[Path]) -> None:
        if not changed_paths:
            log.debug("github_pages: нечего публиковать")
            return
        raise NotImplementedError(
            f"GithubPagesPublisher: этап 2 ({len(changed_paths)} dirty paths). "
            "Нужны GITHUB_PAGES_REPO / GITHUB_TOKEN."
        )
