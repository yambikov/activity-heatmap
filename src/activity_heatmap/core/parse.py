"""Парсер .fit → polyline (lon, lat).

Правило v1: берём только sport=cycling внутри FIT и трек с GPS.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path

import fitdecode

log = logging.getLogger(__name__)

_SEMICIRCLE = 180.0 / (2**31)
_CYCLING = frozenset({"cycling", "bike", "e_biking", "gravel_cycling"})
# indoor / zwift в FIT: sport часто всё равно cycling
_SKIP_SUB_SPORT = frozenset({"virtual_activity", "indoor_cycling"})


@dataclass
class Track:
    points: list[tuple[float, float]]  # (lon, lat)
    sport: str | None = None
    sub_sport: str | None = None
    source_name: str = ""

    @property
    def bbox(self) -> tuple[float, float, float, float] | None:
        if not self.points:
            return None
        lons = [p[0] for p in self.points]
        lats = [p[1] for p in self.points]
        return min(lons), min(lats), max(lons), max(lats)


def _to_degrees(value: float) -> float:
    if abs(value) > 360:
        return value * _SEMICIRCLE
    return value


def _norm_sport(value: object) -> str:
    return str(value).strip().lower().replace(" ", "_")


def parse_fit(path: Path, *, min_points: int = 20, min_span_m: float = 200.0) -> Track | None:
    """Прочитать FIT. None — не cycling / нет GPS / слишком короткий."""
    points: list[tuple[float, float]] = []
    sport: str | None = None
    sub_sport: str | None = None

    with fitdecode.FitReader(path) as fit:
        for frame in fit:
            if frame.frame_type != fitdecode.FIT_FRAME_DATA:
                continue
            if frame.name in ("sport", "session"):
                try:
                    sport = _norm_sport(frame.get_value("sport"))
                except KeyError:
                    pass
                try:
                    sub_sport = _norm_sport(frame.get_value("sub_sport"))
                except KeyError:
                    pass
                continue
            if frame.name != "record":
                continue
            try:
                lat_raw = frame.get_value("position_lat")
                lon_raw = frame.get_value("position_long")
            except KeyError:
                continue
            if lat_raw is None or lon_raw is None:
                continue
            lat = _to_degrees(float(lat_raw))
            lon = _to_degrees(float(lon_raw))
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            try:
                speed = frame.get_value("speed")
                if speed is not None and float(speed) < 0.5:  # м/с — стоянки
                    continue
            except KeyError:
                pass
            points.append((lon, lat))

    if sport is None or sport not in _CYCLING:
        log.debug("skip %s (sport=%r, need cycling)", path.name, sport)
        return None

    if sub_sport is not None and sub_sport in _SKIP_SUB_SPORT:
        log.debug("skip %s (sub_sport=%r)", path.name, sub_sport)
        return None

    if len(points) < min_points:
        log.debug("skip %s (too few GPS points: %d)", path.name, len(points))
        return None

    deduped: list[tuple[float, float]] = [points[0]]
    for p in points[1:]:
        if p != deduped[-1]:
            deduped.append(p)
    points = deduped

    span = _approx_length_m(points)
    if span < min_span_m:
        log.debug("skip %s (span %.0fm)", path.name, span)
        return None

    # «GPS» Zwift Watopia не подходит для карты реального мира
    if _looks_like_zwift_world(points):
        log.debug("skip %s (zwift/virtual GPS world)", path.name)
        return None

    return Track(
        points=points,
        sport=sport,
        sub_sport=sub_sport,
        source_name=path.name,
    )


def _looks_like_zwift_world(points: list[tuple[float, float]]) -> bool:
    """Watopia ≈ lon 166.9 / lat -11.6 (Тихий океан)."""
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    return (
        166.5 < min(lons)
        and max(lons) < 167.5
        and -12.5 < min(lats)
        and max(lats) < -10.5
    )


def _approx_length_m(points: list[tuple[float, float]]) -> float:
    total = 0.0
    for i in range(1, len(points)):
        lon0, lat0 = points[i - 1]
        lon1, lat1 = points[i]
        dlat = (lat1 - lat0) * 111_320.0
        dlon = (lon1 - lon0) * 111_320.0 * math.cos(math.radians((lat0 + lat1) / 2))
        total += math.hypot(dlat, dlon)
    return total
