"""Персист: activities (visit-masks), counts, meta/bbox."""

from __future__ import annotations

import json
import logging
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from activity_heatmap.core.geo import BBox

log = logging.getLogger(__name__)

STATE_VERSION = 1


@dataclass
class Meta:
    version: int
    bbox: BBox | None
    activity_count: int
    count_ref_value: float | None  # кэш перцентиля

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "bbox": asdict(self.bbox) if self.bbox else None,
            "activity_count": self.activity_count,
            "count_ref_value": self.count_ref_value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Meta:
        bbox = None
        if d.get("bbox"):
            b = d["bbox"]
            bbox = BBox(b["west"], b["south"], b["east"], b["north"])
        return cls(
            version=d.get("version", STATE_VERSION),
            bbox=bbox,
            activity_count=d.get("activity_count", 0),
            count_ref_value=d.get("count_ref_value"),
        )


def pack_mask(cells: set[tuple[int, int]]) -> bytes:
    """Сжатый список пар int32 (px, py)."""
    if not cells:
        return zlib.compress(b"", 6)
    arr = np.fromiter(
        (c for xy in sorted(cells) for c in xy),
        dtype=np.int32,
        count=len(cells) * 2,
    )
    return zlib.compress(arr.tobytes(), 6)


def unpack_mask(blob: bytes) -> set[tuple[int, int]]:
    raw = zlib.decompress(blob)
    if not raw:
        return set()
    arr = np.frombuffer(raw, dtype=np.int32)
    return {(int(arr[i]), int(arr[i + 1])) for i in range(0, len(arr), 2)}


class StateStore:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.activities_dir = state_dir / "activities"
        self.counts_path = state_dir / "counts.npz"
        self.meta_path = state_dir / "meta.json"
        self.index_path = state_dir / "activities_index.json"
        self.activities_dir.mkdir(parents=True, exist_ok=True)

        self.meta = self._load_meta()
        self.index: dict[str, dict] = self._load_index()
        self.counts: dict[tuple[int, int], int] = self._load_counts()

    def _load_meta(self) -> Meta:
        if self.meta_path.exists():
            return Meta.from_dict(json.loads(self.meta_path.read_text()))
        return Meta(version=STATE_VERSION, bbox=None, activity_count=0, count_ref_value=None)

    def _load_index(self) -> dict[str, dict]:
        if self.index_path.exists():
            return json.loads(self.index_path.read_text())
        return {}

    def _load_counts(self) -> dict[tuple[int, int], int]:
        if not self.counts_path.exists():
            return {}
        data = np.load(self.counts_path)
        xs = data["x"]
        ys = data["y"]
        cs = data["c"]
        return {(int(xs[i]), int(ys[i])): int(cs[i]) for i in range(len(cs))}

    def has_activity(self, activity_id: str) -> bool:
        return activity_id in self.index

    def load_mask(self, activity_id: str) -> set[tuple[int, int]]:
        path = self.activities_dir / f"{activity_id}.mask"
        if not path.exists():
            return set()
        return unpack_mask(path.read_bytes())

    def save_activity(
        self,
        activity_id: str,
        mask: set[tuple[int, int]],
        *,
        path_name: str,
    ) -> None:
        (self.activities_dir / f"{activity_id}.mask").write_bytes(pack_mask(mask))
        self.index[activity_id] = {
            "path_name": path_name,
            "cells": len(mask),
        }
        self.meta.activity_count = len(self.index)

    def delete_activity(self, activity_id: str) -> None:
        (self.activities_dir / f"{activity_id}.mask").unlink(missing_ok=True)
        self.index.pop(activity_id, None)
        self.meta.activity_count = len(self.index)

    def apply_add(self, mask: set[tuple[int, int]]) -> None:
        for cell in mask:
            self.counts[cell] = self.counts.get(cell, 0) + 1

    def apply_remove(self, mask: set[tuple[int, int]]) -> None:
        for cell in mask:
            c = self.counts.get(cell, 0) - 1
            if c <= 0:
                self.counts.pop(cell, None)
            else:
                self.counts[cell] = c

    def update_bbox(self, track_bbox: tuple[float, float, float, float], margin_m: float) -> None:
        west, south, east, north = track_bbox
        bb = BBox(west, south, east, north).expanded_m(margin_m)
        self.meta.bbox = bb if self.meta.bbox is None else self.meta.bbox.union(bb)

    def recompute_count_ref(self, spec: str) -> float:
        if not self.counts:
            self.meta.count_ref_value = 1.0
            return 1.0
        vals = np.fromiter(self.counts.values(), dtype=np.float64)
        if spec.startswith("p"):
            q = float(spec[1:])
            ref = float(np.percentile(vals, q))
        else:
            ref = float(spec)
        ref = max(ref, 1.0)
        self.meta.count_ref_value = ref
        return ref

    def flush(self) -> None:
        self.meta_path.write_text(json.dumps(self.meta.to_dict(), indent=2))
        self.index_path.write_text(json.dumps(self.index, indent=2, ensure_ascii=False))
        if self.counts:
            xs = np.fromiter((k[0] for k in self.counts), dtype=np.int32, count=len(self.counts))
            ys = np.fromiter((k[1] for k in self.counts), dtype=np.int32, count=len(self.counts))
            cs = np.fromiter(self.counts.values(), dtype=np.int32, count=len(self.counts))
            np.savez_compressed(self.counts_path, x=xs, y=ys, c=cs)
        elif self.counts_path.exists():
            self.counts_path.unlink()

    def clear_all(self) -> None:
        for p in self.activities_dir.glob("*.mask"):
            p.unlink()
        self.index.clear()
        self.counts.clear()
        self.meta = Meta(version=STATE_VERSION, bbox=None, activity_count=0, count_ref_value=None)
        self.flush()
