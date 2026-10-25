"""CLI: activity-heatmap sync | agent | rebuild | add | remove."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from activity_heatmap import __version__
from activity_heatmap.config import load_config
from activity_heatmap.core.lock import LockError, data_lock
from activity_heatmap.core.pipeline import Pipeline
from activity_heatmap.publish import get_publisher


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _build_ingest(config, pipeline, publisher=None):
    try:
        if config.ingest_mode == "local_fs":
            from activity_heatmap.ingest.local_fs import LocalFsIngest

            publish_fn = publisher.publish if publisher is not None else None
            return LocalFsIngest(config, pipeline, publisher=publish_fn)
        if config.ingest_mode == "dropbox_webhook":
            from activity_heatmap.ingest.dropbox_webhook import DropboxWebhookIngest

            return DropboxWebhookIngest()
    except ValueError as e:
        raise click.ClickException(str(e)) from e
    raise click.ClickException(f"Неизвестный INGEST_MODE={config.ingest_mode!r}")


@click.group()
@click.version_option(__version__, prog_name="activity-heatmap")
@click.option("-v", "--verbose", is_flag=True, help="DEBUG-логи")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """XYZ-слой персональных велотреков для nakarte.me."""
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config()


@main.command("sync")
@click.pass_context
def sync_cmd(ctx: click.Context) -> None:
    """Одноразовый полный догон WATCH_DIR ↔ activities + publish."""
    config = ctx.obj["config"]
    try:
        with data_lock(config.lock_path):
            pipeline = Pipeline(config)
            publisher = get_publisher(config)
            ingest = _build_ingest(config, pipeline, publisher)
            dirty = ingest.sync_once()
            publisher.publish(dirty)
            click.echo(
                f"sync: готово, activities={pipeline.store.meta.activity_count} "
                f"dirty={len(dirty)}"
            )
    except LockError as e:
        raise click.ClickException(str(e)) from e


@main.command("agent")
@click.pass_context
def agent_cmd(ctx: click.Context) -> None:
    """Sync на старте, затем FS watch до Ctrl+C."""
    config = ctx.obj["config"]
    try:
        with data_lock(config.lock_path):
            pipeline = Pipeline(config)
            publisher = get_publisher(config)
            ingest = _build_ingest(config, pipeline, publisher)
            dirty = ingest.sync_once()
            publisher.publish(dirty)
            click.echo(
                f"agent: sync-once ok, activities={pipeline.store.meta.activity_count}, "
                "watch…"
            )
            ingest.run_forever()
    except LockError as e:
        raise click.ClickException(str(e)) from e
    except KeyboardInterrupt:
        click.echo("\nagent: остановлен")


@main.command("rerender")
@click.pass_context
def rerender_cmd(ctx: click.Context) -> None:
    """Перерисовать тайлы из state (цвет / z-range) без повторного разбора FIT."""
    config = ctx.obj["config"]
    try:
        with data_lock(config.lock_path):
            pipeline = Pipeline(config)
            publisher = get_publisher(config)
            dirty = pipeline.rerender()
            publisher.publish(dirty)
            click.echo(
                f"rerender: dirty={len(dirty)} color={config.render.color_rgb} "
                f"z={config.render.z_min}..{config.render.z_max}"
            )
    except LockError as e:
        raise click.ClickException(str(e)) from e


@main.command("rebuild")
@click.pass_context
def rebuild_cmd(ctx: click.Context) -> None:
    """Полная пересборка из всех FIT в WATCH_DIR."""
    config = ctx.obj["config"]
    try:
        with data_lock(config.lock_path):
            pipeline = Pipeline(config)
            ingest = _build_ingest(config, pipeline)
            fits = ingest.list_fit_files() if hasattr(ingest, "list_fit_files") else []
            publisher = get_publisher(config)
            dirty = pipeline.rebuild(fits)
            publisher.publish(dirty)
            click.echo(
                f"rebuild: activities={pipeline.store.meta.activity_count} "
                f"dirty={len(dirty)} tiles_dir={config.tiles_dir}"
            )
    except LockError as e:
        raise click.ClickException(str(e)) from e


@main.command("add")
@click.argument("fit_path", type=click.Path(exists=True, path_type=Path))
@click.option("--id", "activity_id", default=None, help="Ключ активности (по умолчанию — content hash)")
@click.pass_context
def add_cmd(ctx: click.Context, fit_path: Path, activity_id: str | None) -> None:
    """Вручную добавить один .fit (offline / отладка)."""
    config = ctx.obj["config"]
    try:
        with data_lock(config.lock_path):
            pipeline = Pipeline(config)
            result = pipeline.add(fit_path, activity_id)
            if result.added:
                get_publisher(config).publish(result.dirty_tiles)
            click.echo(
                f"add: id={result.activity_id[:12]}… added={result.added} "
                f"tiles={len(result.dirty_tiles)} {result.reason}"
            )
    except LockError as e:
        raise click.ClickException(str(e)) from e


@main.command("remove")
@click.argument("activity_id")
@click.pass_context
def remove_cmd(ctx: click.Context, activity_id: str) -> None:
    """Вручную вычесть вклад активности (offline / отладка)."""
    config = ctx.obj["config"]
    try:
        with data_lock(config.lock_path):
            pipeline = Pipeline(config)
            result = pipeline.remove(activity_id)
            if result.removed:
                get_publisher(config).publish(result.dirty_tiles)
            click.echo(
                f"remove: id={result.activity_id[:12]}… removed={result.removed} "
                f"tiles={len(result.dirty_tiles)} {result.reason}"
            )
    except LockError as e:
        raise click.ClickException(str(e)) from e


@main.command("publish")
@click.pass_context
def publish_cmd(ctx: click.Context) -> None:
    """Залить все локальные тайлы в PUBLISH_MODE (первый деплой / полный push)."""
    config = ctx.obj["config"]
    publisher = get_publisher(config)
    try:
        if hasattr(publisher, "publish_all"):
            n = publisher.publish_all()
            url = (
                publisher.tile_url_template()
                if hasattr(publisher, "tile_url_template")
                else config.tile_url_prefix
            )
            click.echo(f"publish: {n} tiles → {config.publish_mode}\n  {url}")
        else:
            paths = sorted(config.tiles_dir.rglob("*.png"))
            publisher.publish(paths)
            click.echo(f"publish: {len(paths)} tiles → {config.publish_mode}")
    except (ValueError, NotImplementedError) as e:
        raise click.ClickException(str(e)) from e
    except Exception as e:
        raise click.ClickException(f"publish failed: {e}") from e


if __name__ == "__main__":
    sys.exit(main())
