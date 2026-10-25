"""Рендер dirty PNG тайлов (Komoot-like линии, один цвет + alpha по частоте)."""

from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
from PIL import Image

from activity_heatmap.config import RenderParams
from activity_heatmap.core.geo import parent_tiles
from activity_heatmap.core.store import StateStore

log = logging.getLogger(__name__)


def alpha_min_for_zoom(z: int, z_max: int, alpha_min: float, alpha_max: float) -> float:
    """При приближении одиночные треки читаемее; на обзоре пол остаётся ниже ради контраста."""
    levels = z_max - z
    if levels <= 1:  # z_max / z_max-1
        boosted = max(alpha_min, 0.48)
    elif levels <= 3:
        boosted = max(alpha_min, alpha_min + 0.14)
    else:
        return alpha_min
    return min(boosted, alpha_max - 0.08)


def alpha_for_count(
    count: int,
    *,
    alpha_min: float,
    alpha_max: float,
    count_ref: float,
) -> float:
    """log-шкала: редкие бледнее, частые плотнее. count_ref лучше брать p99, не p95."""
    t = math.log1p(count) / math.log1p(max(count_ref, 1.0))
    t = max(0.0, min(1.0, t))
    # чуть агрессивнее к верху шкалы — накатанное заметнее
    t = t**0.85
    return alpha_min + (alpha_max - alpha_min) * t


def width_radius_for_count(count: int, count_ref: float) -> int:
    """Доп. толщина (радиус dilation) для частых участков."""
    t = math.log1p(count) / math.log1p(max(count_ref, 1.0))
    if t < 0.35:
        return 0
    if t < 0.7:
        return 1
    return 2


def cells_to_dirty_tiles(
    cells: set[tuple[int, int]] | dict[tuple[int, int], int],
    *,
    z_max: int,
    z_min: int,
) -> set[tuple[int, int, int]]:
    tiles: set[tuple[int, int, int]] = set()
    keys = cells.keys() if isinstance(cells, dict) else cells
    for px, py in keys:
        tx, ty = px // 256, py // 256
        for t in parent_tiles(z_max, tx, ty, z_min):
            tiles.add(t)
    return tiles


def _index_by_zmax_tile(
    counts: dict[tuple[int, int], int],
) -> dict[tuple[int, int], list[tuple[int, int, int]]]:
    by_tile: dict[tuple[int, int], list[tuple[int, int, int]]] = {}
    for (px, py), c in counts.items():
        tx, ty = px // 256, py // 256
        by_tile.setdefault((tx, ty), []).append((px % 256, py % 256, c))
    return by_tile


def render_tiles(
    store: StateStore,
    dirty: set[tuple[int, int, int]],
    *,
    tiles_dir: Path,
    render: RenderParams,
    count_ref: float,
) -> list[Path]:
    written: list[Path] = []
    r, g, b = render.color_rgb
    z_max = render.z_max
    by_tile = _index_by_zmax_tile(store.counts)

    for z, x, y in sorted(dirty):
        a_min = alpha_min_for_zoom(z, z_max, render.alpha_min, render.alpha_max)
        if z == z_max:
            img = _render_zmax(by_tile.get((x, y), []), r, g, b, render, count_ref, a_min)
        else:
            img = _render_from_children(
                by_tile, z, x, y, z_max, r, g, b, render, count_ref, a_min
            )

        out = tiles_dir / str(z) / str(x) / f"{y}.png"
        out.parent.mkdir(parents=True, exist_ok=True)

        extrema = img.getextrema()
        alpha_hi = extrema[3][1] if len(extrema) == 4 else 255
        if alpha_hi == 0:
            if out.exists():
                out.unlink()
                written.append(out)
            continue

        img.save(out, format="PNG", optimize=True)
        written.append(out)

    log.debug("render_tiles: wrote %d / dirty %d", len(written), len(dirty))
    return written


def _paint_alpha(
    arr: np.ndarray,
    ly: int,
    lx: int,
    c: int,
    r: int,
    g: int,
    b: int,
    render: RenderParams,
    count_ref: float,
    alpha_min: float,
) -> None:
    a = alpha_for_count(
        c,
        alpha_min=alpha_min,
        alpha_max=render.alpha_max,
        count_ref=count_ref,
    )
    new_a = int(round(a * 255))
    # если уже нарисовано более частым визитом — не ослаблять
    if new_a <= int(arr[ly, lx, 3]):
        return
    arr[ly, lx, 0] = r
    arr[ly, lx, 1] = g
    arr[ly, lx, 2] = b
    arr[ly, lx, 3] = new_a


def _paint_with_width(
    arr: np.ndarray,
    ly: int,
    lx: int,
    c: int,
    r: int,
    g: int,
    b: int,
    render: RenderParams,
    count_ref: float,
    alpha_min: float,
) -> None:
    rad = width_radius_for_count(c, count_ref) if render.freq_width else 0
    if rad <= 0:
        _paint_alpha(arr, ly, lx, c, r, g, b, render, count_ref, alpha_min)
        return
    r2 = rad * rad
    for dy in range(-rad, rad + 1):
        for dx in range(-rad, rad + 1):
            if dx * dx + dy * dy > r2:
                continue
            ny, nx = ly + dy, lx + dx
            if 0 <= ny < 256 and 0 <= nx < 256:
                _paint_alpha(arr, ny, nx, c, r, g, b, render, count_ref, alpha_min)


def _render_zmax(
    local_cells: list[tuple[int, int, int]],
    r: int,
    g: int,
    b: int,
    render: RenderParams,
    count_ref: float,
    alpha_min: float,
) -> Image.Image:
    arr = np.zeros((256, 256, 4), dtype=np.uint8)
    # сначала редкие, потом частые — частые перекрывают alpha
    for lx, ly, c in sorted(local_cells, key=lambda t: t[2]):
        if 0 <= lx < 256 and 0 <= ly < 256:
            _paint_with_width(arr, ly, lx, c, r, g, b, render, count_ref, alpha_min)
    return Image.fromarray(arr, mode="RGBA")


def _dilate_max(pool: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return pool
    out = pool.copy()
    ys, xs = np.nonzero(pool)
    r2 = radius * radius
    for ly, lx in zip(ys.tolist(), xs.tolist(), strict=True):
        c = int(pool[ly, lx])
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy > r2:
                    continue
                ny, nx = ly + dy, lx + dx
                if 0 <= ny < 256 and 0 <= nx < 256 and c > out[ny, nx]:
                    out[ny, nx] = c
    return out


def _line_radius_for_zoom(z: int, z_max: int, line_width_px: float) -> int:
    levels = z_max - z
    base = max(0, int(round((line_width_px - 1.0) / 2.0)))
    if levels >= 6:
        return max(base, 2)
    if levels >= 3:
        return max(base, 1)
    return base


def _render_from_children(
    by_tile: dict[tuple[int, int], list[tuple[int, int, int]]],
    z: int,
    x: int,
    y: int,
    z_max: int,
    r: int,
    g: int,
    b: int,
    render: RenderParams,
    count_ref: float,
    alpha_min: float,
) -> Image.Image:
    scale = 1 << (z_max - z)
    pool = np.zeros((256, 256), dtype=np.int32)
    base_tx = x * scale
    base_ty = y * scale

    for dy in range(scale):
        for dx in range(scale):
            cells = by_tile.get((base_tx + dx, base_ty + dy))
            if not cells:
                continue
            for lx, ly, c in cells:
                px = dx * 256 + lx
                py = dy * 256 + ly
                olx = px // scale
                oly = py // scale
                if 0 <= olx < 256 and 0 <= oly < 256 and c > pool[oly, olx]:
                    pool[oly, olx] = c

    # базовое утолщение для читаемости на мелких зумах
    pool = _dilate_max(pool, _line_radius_for_zoom(z, z_max, render.line_width_px))

    arr = np.zeros((256, 256, 4), dtype=np.uint8)
    # частые — ещё чуть толще
    items = [(int(ly), int(lx), int(pool[ly, lx])) for ly, lx in zip(*np.nonzero(pool))]
    items.sort(key=lambda t: t[2])
    for ly, lx, c in items:
        _paint_with_width(arr, ly, lx, c, r, g, b, render, count_ref, alpha_min)
    return Image.fromarray(arr, mode="RGBA")
