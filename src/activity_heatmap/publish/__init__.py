"""Publish-адаптеры: github_pages | filesystem | s3."""

from activity_heatmap.publish.base import PublishAdapter, get_publisher

__all__ = ["PublishAdapter", "get_publisher"]
