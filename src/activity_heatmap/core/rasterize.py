"""Растеризация полилинии → visit-mask (мировые пиксели z_max)."""

from __future__ import annotations

import math

from activity_heatmap.core.geo import lonlat_to_world_pixel


def polyline_visit_mask(
    points: list[tuple[float, float]],
    *,
    z_max: int,
    line_width_px: float = 2.0,
) -> set[tuple[int, int]]:
    """Ячейки (px, py), через которые прошла линия (+ толщина)."""
    if len(points) < 2:
        return set()

    pixels: list[tuple[float, float]] = [
        lonlat_to_world_pixel(lon, lat, z_max) for lon, lat in points
    ]

    visited: set[tuple[int, int]] = set()
    half = max(0.0, (line_width_px - 1.0) / 2.0)

    for i in range(1, len(pixels)):
        x0, y0 = pixels[i - 1]
        x1, y1 = pixels[i]
        for px, py in _bresenham(x0, y0, x1, y1):
            if half < 0.25:
                visited.add((px, py))
            else:
                r = int(math.ceil(half))
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        if dx * dx + dy * dy <= half * half + 0.5:
                            visited.add((px + dx, py + dy))
    return visited


def _bresenham(x0: float, y0: float, x1: float, y1: float) -> list[tuple[int, int]]:
    """Суперсэмпл по длине сегмента → целочисленные пиксели."""
    dx = x1 - x0
    dy = y1 - y0
    dist = math.hypot(dx, dy)
    if dist < 1e-9:
        return [(int(round(x0)), int(round(y0)))]
    steps = max(1, int(math.ceil(dist)))
    out: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for i in range(steps + 1):
        t = i / steps
        p = (int(round(x0 + dx * t)), int(round(y0 + dy * t)))
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out
