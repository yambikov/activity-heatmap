"""Базовые тесты конфига и CLI (этап 0)."""

from __future__ import annotations

import os
from pathlib import Path

from activity_heatmap.config import load_config
from activity_heatmap.core.lock import data_lock, LockError
from activity_heatmap.publish import get_publisher


def test_load_config_defaults(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    for key in (
        "WATCH_DIR",
        "PUBLISH_MODE",
        "INGEST_MODE",
        "COLOR_RGB",
        "Z_MAX",
        "ALPHA_MIN",
        "ALPHA_MAX",
        "COUNT_REF",
        "FREQ_WIDTH",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    cfg = load_config()
    assert cfg.render.z_max == 17
    assert cfg.render.color_rgb == (128, 24, 110)
    assert cfg.render.count_ref == "p99"
    assert cfg.publish_mode == "github_pages"
    assert cfg.watch_dir is None


def test_data_lock_exclusive(tmp_path: Path) -> None:
    lock = tmp_path / ".lock"
    with data_lock(lock):
        try:
            with data_lock(lock):
                raise AssertionError("второй lock должен упасть")
        except LockError:
            pass


def test_data_lock_clears_dead_pid(tmp_path: Path) -> None:
    lock = tmp_path / ".lock"
    # заведомо мёртвый pid
    lock.write_text("999999991\n0\n")
    with data_lock(lock):
        assert lock.is_file()


def test_get_publisher_filesystem(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PUBLISH_MODE", "filesystem")
    cfg = load_config()
    pub = get_publisher(cfg)
    pub.publish([])  # no-op ok
