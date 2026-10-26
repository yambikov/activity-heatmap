"""Контракт ядра: add / remove / rebuild."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from activity_heatmap.config import Config
from activity_heatmap.core.ids import activity_id_for_file
from activity_heatmap.core.parse import parse_fit
from activity_heatmap.core.rasterize import polyline_visit_mask
from activity_heatmap.core.render import cells_to_dirty_tiles, render_tiles
from activity_heatmap.core.store import StateStore
from activity_heatmap.logutil import bold, cyan, dim, green, yellow

log = logging.getLogger(__name__)


@dataclass
class AddResult:
    activity_id: str
    added: bool
    dirty_tiles: list[Path] = field(default_factory=list)
    reason: str = ""


@dataclass
class RemoveResult:
    activity_id: str
    removed: bool
    dirty_tiles: list[Path] = field(default_factory=list)
    reason: str = ""


class Pipeline:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        self.config.tiles_dir.mkdir(parents=True, exist_ok=True)
        self.store = StateStore(self.config.state_dir)

    def add(self, fit_path: Path, activity_id: str | None = None) -> AddResult:
        aid = activity_id or activity_id_for_file(fit_path)
        if self.store.has_activity(aid):
            return AddResult(activity_id=aid, added=False, reason="already present")

        track = parse_fit(fit_path)
        if track is None:
            return AddResult(activity_id=aid, added=False, reason="skipped (no usable GPS)")

        mask = polyline_visit_mask(
            track.points,
            z_max=self.config.render.z_max,
            line_width_px=self.config.render.line_width_px,
        )
        if not mask:
            return AddResult(activity_id=aid, added=False, reason="empty mask")

        self.store.apply_add(mask)
        self.store.save_activity(aid, mask, path_name=fit_path.name)
        if track.bbox:
            self.store.update_bbox(track.bbox, self.config.render.bbox_margin_m)

        count_ref = self.store.recompute_count_ref(self.config.render.count_ref)
        dirty = cells_to_dirty_tiles(
            mask,
            z_max=self.config.render.z_max,
            z_min=self.config.render.z_min,
        )
        paths = render_tiles(
            self.store,
            dirty,
            tiles_dir=self.config.tiles_dir,
            render=self.config.render,
            count_ref=count_ref,
        )
        self.store.flush()
        log.debug(
            "add %s cells=%d tiles=%d id=%s",
            fit_path.name,
            len(mask),
            len(paths),
            aid[:12],
        )
        return AddResult(activity_id=aid, added=True, dirty_tiles=paths)

    def remove(self, activity_id: str) -> RemoveResult:
        if not self.store.has_activity(activity_id):
            return RemoveResult(activity_id=activity_id, removed=False, reason="not found")

        mask = self.store.load_mask(activity_id)
        self.store.apply_remove(mask)
        self.store.delete_activity(activity_id)

        count_ref = self.store.recompute_count_ref(self.config.render.count_ref)
        dirty = cells_to_dirty_tiles(
            mask,
            z_max=self.config.render.z_max,
            z_min=self.config.render.z_min,
        )
        paths = render_tiles(
            self.store,
            dirty,
            tiles_dir=self.config.tiles_dir,
            render=self.config.render,
            count_ref=count_ref,
        )
        self.store.flush()
        log.debug(
            "remove id=%s cells=%d tiles=%d",
            activity_id[:12],
            len(mask),
            len(paths),
        )
        return RemoveResult(activity_id=activity_id, removed=True, dirty_tiles=paths)

    def rerender(self) -> list[Path]:
        """Перерисовать все тайлы из текущего counts (смена цвета / z-range без повторного parse)."""
        for p in self.config.tiles_dir.rglob("*.png"):
            p.unlink(missing_ok=True)
        if not self.store.counts:
            log.warning("rerender: counts пуст")
            return []
        count_ref = self.store.recompute_count_ref(self.config.render.count_ref)
        dirty = cells_to_dirty_tiles(
            self.store.counts,
            z_max=self.config.render.z_max,
            z_min=self.config.render.z_min,
        )
        paths = render_tiles(
            self.store,
            dirty,
            tiles_dir=self.config.tiles_dir,
            render=self.config.render,
            count_ref=count_ref,
        )
        self.store.flush()
        log.info("rerender done: tiles=%d color=%s", len(paths), self.config.render.color_rgb)
        return paths

    def rebuild(self, fit_paths: list[Path]) -> list[Path]:
        """Полная пересборка: очистить state, add все пригодные FIT."""
        total = len(fit_paths)
        log.info(
            "%s полная пересборка из %s файлов  (z=%s..%s)",
            bold("Rebuild"),
            cyan(str(total)),
            self.config.render.z_min,
            self.config.render.z_max,
        )
        old_tiles = list(self.config.tiles_dir.rglob("*.png"))
        if old_tiles:
            log.info("%s стираю старые PNG: %s шт.", yellow("1/3"), cyan(str(len(old_tiles))))
        for p in old_tiles:
            p.unlink(missing_ok=True)

        self.store.clear_all()
        log.info("%s разбираю FIT и коплю маски…", yellow("2/3"))
        dirty_all: set[tuple[int, int, int]] = set()
        added = 0
        skipped = 0
        for i, path in enumerate(fit_paths, 1):
            track = parse_fit(path)
            if track is None:
                skipped += 1
                if i == 1 or i % 25 == 0 or i == total:
                    log.info(
                        "  [%s/%s] %s  %s",
                        cyan(str(i)),
                        total,
                        dim(_short_name(path.name)),
                        yellow("skip"),
                    )
                continue
            aid = activity_id_for_file(path)
            mask = polyline_visit_mask(
                track.points,
                z_max=self.config.render.z_max,
                line_width_px=self.config.render.line_width_px,
            )
            if not mask:
                skipped += 1
                continue
            self.store.apply_add(mask)
            self.store.save_activity(aid, mask, path_name=path.name)
            if track.bbox:
                self.store.update_bbox(track.bbox, self.config.render.bbox_margin_m)
            dirty_all |= cells_to_dirty_tiles(
                mask,
                z_max=self.config.render.z_max,
                z_min=self.config.render.z_min,
            )
            added += 1
            # частый flush — при обрыве не теряем уже посчитанное
            if added % 5 == 0:
                self.store.flush()
            if i == 1 or added % 10 == 0 or i == total:
                log.info(
                    "  [%s/%s] %s  вело=%s  skip=%s  dirty≈%s",
                    cyan(str(i)),
                    total,
                    green("ok"),
                    green(str(added)),
                    yellow(str(skipped)),
                    cyan(str(len(dirty_all))),
                )

        self.store.flush()
        log.info(
            "%s рисую PNG: ~%s тайлов (это может занять несколько минут)…",
            yellow("3/3"),
            cyan(str(len(dirty_all))),
        )
        count_ref = self.store.recompute_count_ref(self.config.render.count_ref)
        paths = render_tiles(
            self.store,
            dirty_all,
            tiles_dir=self.config.tiles_dir,
            render=self.config.render,
            count_ref=count_ref,
        )
        self.store.flush()
        log.info(
            "%s activities=%s  png=%s  skip=%s",
            green("✓ rebuild готов"),
            bold(str(added)),
            cyan(str(len(paths))),
            yellow(str(skipped)),
        )
        return paths


def _short_name(name: str, limit: int = 48) -> str:
    if len(name) <= limit:
        return name
    return name[: limit - 1] + "…"
