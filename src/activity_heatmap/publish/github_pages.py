"""Publish: commit/push dirty tiles в gh-pages под секретным путём.

Публичный URL:
  https://<user>.github.io/<repo>/<PAGES_SECRET_PATH>/activity-heatmap/{z}/{x}/{y}.png

Это obscurity (не угадать URL), не настоящая auth: в публичном репо
имя сегмента видно в дереве ветки gh-pages — не светите репо в профиле.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from activity_heatmap.config import Config
from activity_heatmap.logutil import bold, cyan, dim, green, magenta
from activity_heatmap.publish.base import PublishAdapter

log = logging.getLogger(__name__)


class GithubPagesPublisher(PublishAdapter):
    def __init__(self, config: Config) -> None:
        self.config = config

    def publish(self, changed_paths: list[Path]) -> None:
        if not changed_paths:
            log.debug("github_pages: нечего публиковать")
            return
        self._validate()
        log.info(
            "%s готовлю %s файлов → ветка %s",
            magenta("Pages"),
            cyan(str(len(changed_paths))),
            dim(self.config.github_pages_branch),
        )
        worktree = self._ensure_worktree()
        dest_root = worktree / self.config.pages_secret_path / "activity-heatmap"
        tiles_dir = self.config.tiles_dir.resolve()

        n_written = 0
        n_deleted = 0
        for src in changed_paths:
            src = Path(src).resolve()
            try:
                rel = src.relative_to(tiles_dir)
            except ValueError:
                log.warning("github_pages: skip вне tiles_dir: %s", src)
                continue
            dest = dest_root / rel
            if src.is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                n_written += 1
            elif dest.is_file():
                dest.unlink()
                n_deleted += 1
                self._prune_empty(dest.parent, stop_at=dest_root)

        if n_written == 0 and n_deleted == 0:
            log.info("github_pages: нет валидных dirty paths")
            return

        self._commit_and_push(worktree, n_written, n_deleted)

    def publish_all(self) -> int:
        """Залить все локальные PNG (первый деплой)."""
        paths = sorted(self.config.tiles_dir.rglob("*.png"))
        self.publish(paths)
        return len(paths)

    def tile_url_template(self) -> str:
        """Шаблон XYZ для nakarte (…/{z}/{x}/{y}.png)."""
        prefix = self.config.tile_url_prefix.rstrip("/")
        return f"{prefix}/{{z}}/{{x}}/{{y}}.png"

    def _validate(self) -> None:
        if not self.config.github_pages_repo.strip():
            raise ValueError(
                "GITHUB_PAGES_REPO не задан (формат owner/repo)"
            )
        secret = self.config.pages_secret_path.strip()
        if not secret:
            raise ValueError("PAGES_SECRET_PATH не задан (длинный случайный токен)")
        if "/" in secret or "\\" in secret or secret in (".", ".."):
            raise ValueError("PAGES_SECRET_PATH должен быть одним сегментом пути")
        if len(secret) < 16:
            raise ValueError("PAGES_SECRET_PATH слишком короткий (минимум 16 символов)")

    def _remote_url(self) -> str:
        repo = self.config.github_pages_repo.strip()
        token = self.config.github_token.strip()
        if token:
            return f"https://x-access-token:{token}@github.com/{repo}.git"
        return f"git@github.com:{repo}.git"

    def _worktree_path(self) -> Path:
        return self.config.data_dir / ".publish" / "gh-pages"

    def _ensure_worktree(self) -> Path:
        work = self._worktree_path()
        branch = self.config.github_pages_branch
        remote = self._remote_url()
        marker = work / ".git"

        if marker.exists() or (work / ".git").is_file():
            self._run(["git", "remote", "set-url", "origin", remote], cwd=work)
            self._run(["git", "fetch", "origin", branch], cwd=work, check=False)
            # если ветка уже есть удалённо — жёстко синхронизируемся
            rc = self._run(
                ["git", "rev-parse", "--verify", f"origin/{branch}"],
                cwd=work,
                check=False,
                capture=True,
            )
            if rc.returncode == 0:
                self._run(["git", "checkout", "-B", branch, f"origin/{branch}"], cwd=work)
            else:
                self._run(["git", "checkout", "-B", branch], cwd=work)
        else:
            work.parent.mkdir(parents=True, exist_ok=True)
            if work.exists():
                shutil.rmtree(work)
            # пробуем clone существующей ветки Pages
            clone = self._run(
                [
                    "git",
                    "clone",
                    "--branch",
                    branch,
                    "--single-branch",
                    remote,
                    str(work),
                ],
                check=False,
                capture=True,
            )
            if clone.returncode != 0:
                # ветки ещё нет — orphan
                work.mkdir(parents=True, exist_ok=True)
                self._run(["git", "init", "-b", branch], cwd=work)
                self._run(["git", "remote", "add", "origin", remote], cwd=work)

        # GitHub Pages: не пропускать «скрытые» пути через Jekyll
        nojekyll = work / ".nojekyll"
        if not nojekyll.exists():
            nojekyll.write_text("", encoding="utf-8")

        return work

    def _commit_and_push(self, work: Path, n_written: int, n_deleted: int) -> None:
        branch = self.config.github_pages_branch
        self._run(["git", "add", "-A"], cwd=work)
        status = self._run(
            ["git", "status", "--porcelain"],
            cwd=work,
            capture=True,
        )
        if not (status.stdout or "").strip():
            log.info("%s commit не нужен — уже актуально", green("Pages"))
            return

        msg = f"tiles: +{n_written} −{n_deleted}"
        log.info("%s commit %s…", magenta("Pages"), dim(msg))
        self._run(
            [
                "git",
                "-c",
                "user.email=activity-heatmap@local",
                "-c",
                "user.name=activity-heatmap",
                "commit",
                "-m",
                msg,
            ],
            cwd=work,
        )
        log.info("%s push в %s …", magenta("Pages"), bold(self.config.github_pages_repo))
        self._run(["git", "push", "-u", "origin", f"HEAD:{branch}"], cwd=work)
        log.info(
            "%s +%s −%s → %s",
            green("✓ push ok"),
            cyan(str(n_written)),
            dim(str(n_deleted)),
            bold(self.config.github_pages_repo),
        )

    @staticmethod
    def _prune_empty(start: Path, stop_at: Path) -> None:
        cur = start
        stop_at = stop_at.resolve()
        while cur.resolve() != stop_at and cur.is_dir():
            try:
                next(cur.iterdir())
                break
            except StopIteration:
                parent = cur.parent
                cur.rmdir()
                cur = parent

    @staticmethod
    def _run(
        cmd: list[str],
        *,
        cwd: Path | None = None,
        check: bool = True,
        capture: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        # не логируем remote URL — там может быть token
        log.debug("git: %s", " ".join(cmd[:3] + (["…"] if len(cmd) > 3 else [])))
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=False,
            text=True,
            capture_output=True,
        )
        if check and result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"git failed ({' '.join(cmd[:4])}): {err}")
        return result
