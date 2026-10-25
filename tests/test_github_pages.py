"""Publish github_pages: secret path + orphan worktree push (local bare remote)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from activity_heatmap.config import Config, RenderParams
from activity_heatmap.publish.github_pages import GithubPagesPublisher


def _cfg(tmp: Path, *, secret: str, repo: str) -> Config:
    return Config(
        data_dir=tmp / "data",
        watch_dir=None,
        ingest_mode="local_fs",
        publish_mode="github_pages",
        tile_url_prefix=f"https://example.github.io/repo/{secret}/activity-heatmap",
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
        github_pages_repo=repo,
        github_pages_branch="gh-pages",
        github_token="",
        pages_secret_path=secret,
    )


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_publish_under_secret_path(tmp_path: Path, monkeypatch) -> None:
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", str(bare))

    # GithubPagesPublisher использует git@github.com:… — подменим remote URL на bare
    secret = "s3cretTokenPathForTest01"
    cfg = _cfg(tmp_path, secret=secret, repo="owner/does-not-matter")
    tiles = cfg.tiles_dir
    png = tiles / "12" / "1" / "2.png"
    png.parent.mkdir(parents=True)
    png.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    pub = GithubPagesPublisher(cfg)
    monkeypatch.setattr(pub, "_remote_url", lambda: str(bare))

    pub.publish([png])

    check = tmp_path / "check"
    _git(tmp_path, "clone", "-b", "gh-pages", str(bare), str(check))
    assert (check / secret / "activity-heatmap" / "12" / "1" / "2.png").is_file()
    assert (check / ".nojekyll").is_file()


def test_reject_short_secret(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, secret="short", repo="a/b")
    pub = GithubPagesPublisher(cfg)
    try:
        pub.publish([tmp_path / "x.png"])
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "PAGES_SECRET_PATH" in str(e)
