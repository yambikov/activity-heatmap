"""Этап 2: sync reconcile папка ↔ activities."""

from __future__ import annotations

from pathlib import Path

from activity_heatmap.config import Config, RenderParams
from activity_heatmap.core.ids import activity_id_for_file
from activity_heatmap.core.pipeline import Pipeline
from activity_heatmap.ingest.local_fs import LocalFsIngest


def _cfg(tmp: Path, watch: Path) -> Config:
    return Config(
        data_dir=tmp / "data",
        watch_dir=watch,
        ingest_mode="local_fs",
        publish_mode="filesystem",
        tile_url_prefix="http://test",
        render=RenderParams(
            color_rgb=(128, 24, 110),
            alpha_min=0.28,
            alpha_max=0.96,
            count_ref="p99",
            line_width_px=2.0,
            z_min=12,
            z_max=14,
            bbox_margin_m=500,
            freq_width=False,
        ),
        github_pages_repo="",
        github_pages_branch="gh-pages",
        github_token="",
    )


def test_sync_add_remove_idempotent(tmp_path: Path, monkeypatch) -> None:
    from activity_heatmap.core import pipeline as pl
    from activity_heatmap.core.parse import Track

    watch = tmp_path / "watch"
    watch.mkdir()
    f1 = watch / "ride1.fit"
    f1.write_bytes(b"fit-content-one")
    f2 = watch / "ride2.fit"
    f2.write_bytes(b"fit-content-two")

    tracks = {
        "ride1.fit": Track(
            points=[(37.60 + i * 0.0004, 55.75) for i in range(30)],
            sport="cycling",
            source_name="ride1.fit",
        ),
        "ride2.fit": Track(
            points=[(37.61 + i * 0.0004, 55.751) for i in range(30)],
            sport="cycling",
            source_name="ride2.fit",
        ),
    }

    def fake_parse(path: Path, **kwargs):
        return tracks.get(path.name)

    monkeypatch.setattr(pl, "parse_fit", fake_parse)

    cfg = _cfg(tmp_path, watch)
    pipe = Pipeline(cfg)
    ingest = LocalFsIngest(cfg, pipe)

    dirty1 = ingest.sync_once()
    assert pipe.store.meta.activity_count == 2
    assert dirty1

    # повтор — no-op
    dirty2 = ingest.sync_once()
    assert dirty2 == []
    assert pipe.store.meta.activity_count == 2

    # удалили файл — вычитаем вклад
    aid1 = activity_id_for_file(f1)
    f1.unlink()
    dirty3 = ingest.sync_once()
    assert aid1 not in pipe.store.index
    assert pipe.store.meta.activity_count == 1
    assert dirty3
