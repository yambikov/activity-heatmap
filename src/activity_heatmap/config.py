"""Конфиг из env / .env. Ядро не знает про GitHub/VDS — только DATA_DIR и параметры рендера."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _parse_rgb(value: str) -> tuple[int, int, int]:
    parts = [int(p.strip()) for p in value.split(",")]
    if len(parts) != 3:
        raise ValueError(f"COLOR_RGB must be R,G,B got {value!r}")
    return parts[0], parts[1], parts[2]


@dataclass(frozen=True)
class RenderParams:
    color_rgb: tuple[int, int, int]
    alpha_min: float
    alpha_max: float
    count_ref: str  # "p95" / "p99" или число
    line_width_px: float
    z_min: int
    z_max: int
    bbox_margin_m: float
    freq_width: bool  # толще линии на частых участках


@dataclass(frozen=True)
class Config:
    data_dir: Path
    watch_dir: Path | None
    ingest_mode: str
    publish_mode: str
    tile_url_prefix: str
    render: RenderParams
    github_pages_repo: str
    github_pages_branch: str
    github_token: str
    pages_secret_path: str  # сегмент URL / ветки Pages; obscurity, не auth

    @property
    def state_dir(self) -> Path:
        return self.data_dir / "state"

    @property
    def tiles_dir(self) -> Path:
        return self.data_dir / "tiles" / "activity-heatmap"

    @property
    def lock_path(self) -> Path:
        return self.state_dir / ".lock"

    @property
    def pages_tiles_prefix(self) -> str:
        """Относительный путь тайлов внутри gh-pages: <secret>/activity-heatmap."""
        secret = self.pages_secret_path.strip().strip("/")
        return f"{secret}/activity-heatmap" if secret else "activity-heatmap"


def load_config(env_file: str | Path | None = None) -> Config:
    # Не ищем .env вверх по дереву — иначе тесты подхватывают проектный .env.
    if env_file is not None:
        load_dotenv(env_file, override=False)
    else:
        cwd_env = Path.cwd() / ".env"
        if cwd_env.is_file():
            load_dotenv(cwd_env, override=False)

    data_dir = Path(os.getenv("DATA_DIR", "./data")).expanduser().resolve()
    watch_raw = os.getenv("WATCH_DIR", "").strip()
    watch_dir = Path(watch_raw).expanduser().resolve() if watch_raw else None

    render = RenderParams(
        color_rgb=_parse_rgb(os.getenv("COLOR_RGB", "128,24,110")),
        alpha_min=float(os.getenv("ALPHA_MIN", "0.28")),
        alpha_max=float(os.getenv("ALPHA_MAX", "0.96")),
        count_ref=os.getenv("COUNT_REF", "p99"),
        line_width_px=float(os.getenv("LINE_WIDTH_PX", "2.5")),
        z_min=int(os.getenv("Z_MIN", "5")),
        z_max=int(os.getenv("Z_MAX", "17")),
        bbox_margin_m=float(os.getenv("BBOX_MARGIN_M", "2000")),
        freq_width=os.getenv("FREQ_WIDTH", "1").strip() not in ("0", "false", "False", ""),
    )

    return Config(
        data_dir=data_dir,
        watch_dir=watch_dir,
        ingest_mode=os.getenv("INGEST_MODE", "local_fs"),
        publish_mode=os.getenv("PUBLISH_MODE", "github_pages"),
        tile_url_prefix=os.getenv(
            "TILE_URL_PREFIX",
            "https://example.github.io/tiles/activity-heatmap",
        ),
        render=render,
        github_pages_repo=os.getenv("GITHUB_PAGES_REPO", ""),
        github_pages_branch=os.getenv("GITHUB_PAGES_BRANCH", "gh-pages"),
        github_token=os.getenv("GITHUB_TOKEN", ""),
        pages_secret_path=os.getenv("PAGES_SECRET_PATH", "").strip(),
    )
