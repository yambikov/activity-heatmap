"""Этап 1: add → линия есть; remove → вклад исчез."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from activity_heatmap.config import Config, RenderParams
from activity_heatmap.core.pipeline import Pipeline
from activity_heatmap.core.rasterize import polyline_visit_mask
from activity_heatmap.core.render import alpha_for_count


def _cfg(tmp: Path) -> Config:
    return Config(
        data_dir=tmp / "data",
        watch_dir=None,
        ingest_mode="local_fs",
        publish_mode="filesystem",
        tile_url_prefix="http://test",
        render=RenderParams(
            color_rgb=(128, 24, 110),
            alpha_min=0.28,
            alpha_max=0.96,
            count_ref="p99",
            line_width_px=2.5,
            z_min=10,
            z_max=14,
            bbox_margin_m=500,
            freq_width=True,
        ),
        github_pages_repo="",
        github_pages_branch="gh-pages",
        github_token="",
    )


def test_visit_mask_covers_line() -> None:
    # короткая линия в Москве
    pts = [(37.6, 55.75), (37.61, 55.75), (37.61, 55.751)]
    mask = polyline_visit_mask(pts, z_max=14, line_width_px=2.0)
    assert len(mask) > 10


def test_alpha_monotone() -> None:
    a1 = alpha_for_count(1, alpha_min=0.28, alpha_max=0.96, count_ref=10)
    a5 = alpha_for_count(5, alpha_min=0.28, alpha_max=0.96, count_ref=10)
    a10 = alpha_for_count(10, alpha_min=0.28, alpha_max=0.96, count_ref=10)
    assert 0.28 <= a1 < a5 < a10 <= 0.96
    # одиночный заметно бледнее накатанного
    assert a10 - a1 > 0.25


def test_alpha_min_boost_when_zoomed_in() -> None:
    from activity_heatmap.core.render import alpha_min_for_zoom

    base = 0.28
    close = alpha_min_for_zoom(15, 15, base, 0.96)
    far = alpha_min_for_zoom(8, 15, base, 0.96)
    assert close > far
    assert close >= 0.48
    a1_close = alpha_for_count(1, alpha_min=close, alpha_max=0.96, count_ref=10)
    a1_far = alpha_for_count(1, alpha_min=far, alpha_max=0.96, count_ref=10)
    assert a1_close > a1_far


def test_add_remove_synthetic(tmp_path: Path, monkeypatch) -> None:
    """Синтетический FIT не нужен — мокаем parse_fit."""
    from activity_heatmap.core import pipeline as pl
    from activity_heatmap.core.parse import Track

    track = Track(
        points=[(37.60 + i * 0.0005, 55.75) for i in range(40)],
        sport="cycling",
        source_name="synthetic.fit",
    )
    monkeypatch.setattr(pl, "parse_fit", lambda path: track)

    cfg = _cfg(tmp_path)
    pipe = Pipeline(cfg)
    fake = tmp_path / "a.fit"
    fake.write_bytes(b"fake-fit-content-aaa")

    r1 = pipe.add(fake, activity_id="act1")
    assert r1.added
    assert pipe.store.counts
    assert any(cfg.tiles_dir.rglob("*.png"))

    # повтор — no-op
    r2 = pipe.add(fake, activity_id="act1")
    assert not r2.added

    # второй трек чуть севернее — counts растут на пересечении если есть
    track2 = Track(
        points=[(37.60 + i * 0.0005, 55.7502) for i in range(40)],
        sport="cycling",
        source_name="synthetic2.fit",
    )
    monkeypatch.setattr(pl, "parse_fit", lambda path: track2)
    fake2 = tmp_path / "b.fit"
    fake2.write_bytes(b"fake-fit-content-bbb")
    assert pipe.add(fake2, activity_id="act2").added

    before = dict(pipe.store.counts)
    rem = pipe.remove("act1")
    assert rem.removed
    assert "act1" not in pipe.store.index
    # ячейки только из act1 должны уйти или уменьшиться
    for cell, c in before.items():
        after = pipe.store.counts.get(cell, 0)
        assert after <= c
        assert after >= 0


def test_tile_png_has_alpha(tmp_path: Path, monkeypatch) -> None:
    from activity_heatmap.core import pipeline as pl
    from activity_heatmap.core.parse import Track

    track = Track(
        points=[(37.62 + i * 0.0003, 55.76) for i in range(50)],
        sport="cycling",
        source_name="t.fit",
    )
    monkeypatch.setattr(pl, "parse_fit", lambda path: track)
    cfg = _cfg(tmp_path)
    pipe = Pipeline(cfg)
    f = tmp_path / "t.fit"
    f.write_bytes(b"tile-png-test")
    pipe.add(f, activity_id="t1")
    pngs = list(cfg.tiles_dir.rglob("*.png"))
    assert pngs
    img = Image.open(pngs[0])
    assert img.mode == "RGBA"
    arr = np.array(img)
    assert arr[..., 3].max() > 0
