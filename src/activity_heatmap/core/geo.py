"""Web Mercator и XYZ-пиксели на z_max."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Web Mercator limits
_LAT_MAX = 85.05112878
_ORIGIN_SHIFT = 20037508.342789244  # π * 6378137


@dataclass(frozen=True)
class BBox:
    west: float
    south: float
    east: float
    north: float

    def expanded_m(self, margin_m: float) -> BBox:
        """Расширить bbox примерно на margin_m метров."""
        mid_lat = (self.south + self.north) / 2.0
        dlat = margin_m / 111_320.0
        dlon = margin_m / (111_320.0 * max(0.2, math.cos(math.radians(mid_lat))))
        return BBox(
            west=self.west - dlon,
            south=max(-_LAT_MAX, self.south - dlat),
            east=self.east + dlon,
            north=min(_LAT_MAX, self.north + dlat),
        )

    def union(self, other: BBox) -> BBox:
        return BBox(
            west=min(self.west, other.west),
            south=min(self.south, other.south),
            east=max(self.east, other.east),
            north=max(self.north, other.north),
        )

    def contains_point(self, lon: float, lat: float) -> bool:
        return self.west <= lon <= self.east and self.south <= lat <= self.north


def clamp_lat(lat: float) -> float:
    return max(-_LAT_MAX, min(_LAT_MAX, lat))


def lonlat_to_mercator(lon: float, lat: float) -> tuple[float, float]:
    lat = clamp_lat(lat)
    x = lon * _ORIGIN_SHIFT / 180.0
    y = math.log(math.tan((90.0 + lat) * math.pi / 360.0)) * _ORIGIN_SHIFT / math.pi
    return x, y


def lonlat_to_world_pixel(lon: float, lat: float, z: int) -> tuple[float, float]:
    """Непрерывные мировые пиксели XYZ (256 * 2^z на сторону)."""
    lat = clamp_lat(lat)
    n = 256 * (1 << z)
    x = (lon + 180.0) / 360.0 * n
    sin_lat = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * n
    return x, y


def world_pixel_to_tile(px: int, py: int, z: int) -> tuple[int, int, int, int]:
    """(tile_x, tile_y, local_x, local_y)."""
    tx, lx = divmod(px, 256)
    ty, ly = divmod(py, 256)
    return tx, ty, lx, ly


def tile_pixel_bounds(z: int, x: int, y: int) -> tuple[int, int, int, int]:
    """Мировые пиксели [px0, px1) × [py0, py1) для тайла."""
    return x * 256, y * 256, (x + 1) * 256, (y + 1) * 256


def parent_tiles(z: int, x: int, y: int, z_min: int) -> list[tuple[int, int, int]]:
    out = [(z, x, y)]
    cz, cx, cy = z, x, y
    while cz > z_min:
        cz -= 1
        cx //= 2
        cy //= 2
        out.append((cz, cx, cy))
    return out
