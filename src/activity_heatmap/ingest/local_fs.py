"""Ingest v1: локальная папка WATCH_DIR (iCloud / Dropbox / …)."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from activity_heatmap.config import Config
from activity_heatmap.core.ids import activity_id_for_file
from activity_heatmap.core.pipeline import Pipeline
from activity_heatmap.ingest.base import IngestAdapter
from activity_heatmap.logutil import bold, cyan, dim, green, magenta, red, yellow

log = logging.getLogger(__name__)

PublishFn = Callable[[list[Path]], None]


def _short(name: str, limit: int = 52) -> str:
    if len(name) <= limit:
        return name
    return name[: limit - 1] + "…"


class LocalFsIngest(IngestAdapter):
    """sync-once + FS watch на папку Dropbox Desktop."""

    def __init__(
        self,
        config: Config,
        pipeline: Pipeline,
        *,
        publisher: PublishFn | None = None,
        debounce_s: float = 1.5,
    ) -> None:
        if config.watch_dir is None:
            raise ValueError("WATCH_DIR обязателен для INGEST_MODE=local_fs")
        self.config = config
        self.pipeline = pipeline
        self.watch_dir = config.watch_dir
        self.publisher = publisher
        self.debounce_s = debounce_s
        self._skipped_path = config.state_dir / "skipped.json"
        self._skipped: dict[str, str] = self._load_skipped()

    def list_fit_files(self) -> list[Path]:
        if not self.watch_dir.is_dir():
            log.warning("%s WATCH_DIR не существует: %s", yellow("нет папки"), self.watch_dir)
            return []
        return sorted(
            p
            for p in self.watch_dir.rglob("*")
            if p.is_file() and p.suffix.lower() == ".fit"
        )

    def sync_once(self) -> list[Path]:
        """Сверить WATCH_DIR ↔ activities: add новые, remove исчезнувшие."""
        fits = self.list_fit_files()
        log.info(
            "%s в папке: %s .fit  %s",
            bold("Скан"),
            cyan(str(len(fits))),
            dim(str(self.watch_dir)),
        )

        present: dict[str, Path] = {}
        for path in fits:
            try:
                aid = activity_id_for_file(path)
            except OSError as e:
                log.warning("%s %s — %s", yellow("не прочитать"), path.name, e)
                continue
            present[aid] = path

        to_remove = [aid for aid in self.pipeline.store.index if aid not in present]
        to_add: list[tuple[str, Path]] = []
        known_skip = 0
        for aid, path in present.items():
            if self.pipeline.store.has_activity(aid):
                continue
            if aid in self._skipped:
                known_skip += 1
                continue
            to_add.append((aid, path))

        # убрать пометки для файлов, которых больше нет в папке
        for aid in [a for a in self._skipped if a not in present]:
            del self._skipped[aid]

        already = len(present) - len(to_add) - known_skip
        log.info(
            "%s  новых=%s  исчезло=%s  уже в базе=%s  ранее-skip=%s",
            bold("План"),
            green(str(len(to_add))),
            red(str(len(to_remove))) if to_remove else dim("0"),
            cyan(str(max(0, already))),
            dim(str(known_skip)),
        )
        if not to_add and not to_remove:
            self._save_skipped()
            log.info("%s менять нечего — слой актуален", green("✓"))
            return []

        dirty: list[Path] = []
        added = removed = skipped = 0

        if to_remove:
            log.info("%s %s активностей…", red("− удаляю"), bold(str(len(to_remove))))
            for i, aid in enumerate(to_remove, 1):
                result = self.pipeline.remove(aid)
                if result.removed:
                    removed += 1
                    dirty.extend(result.dirty_tiles)
                    self._skipped.pop(aid, None)
                    log.info(
                        "  %s [%d/%d] id=%s…  тайлов=%s",
                        red("удалён"),
                        i,
                        len(to_remove),
                        aid[:12],
                        cyan(str(len(result.dirty_tiles))),
                    )

        if to_add:
            log.info("%s %s файлов…", green("+ добавляю"), bold(str(len(to_add))))
            for i, (aid, path) in enumerate(to_add, 1):
                result = self.pipeline.add(path, aid)
                if result.added:
                    added += 1
                    dirty.extend(result.dirty_tiles)
                    self._skipped.pop(aid, None)
                    log.info(
                        "  %s [%d/%d] %s  → тайлов %s",
                        green("загружен"),
                        i,
                        len(to_add),
                        _short(path.name),
                        cyan(str(len(result.dirty_tiles))),
                    )
                else:
                    reason = result.reason or "skipped"
                    # навсегда: без GPS / не cycling / empty mask — не гоняем снова
                    self._skipped[aid] = f"{path.name}: {reason}"
                    log.info(
                        "  %s [%d/%d] %s — %s",
                        yellow("пропуск"),
                        i,
                        len(to_add),
                        _short(path.name),
                        dim(reason),
                    )
                    skipped += 1

        self._save_skipped()
        uniq = list(dict.fromkeys(dirty))
        log.info(
            "%s  +%s  −%s  skip=%s  dirty=%s  всего_активностей=%s",
            bold("Итог"),
            green(str(added)),
            red(str(removed)),
            yellow(str(skipped)),
            cyan(str(len(uniq))),
            bold(str(self.pipeline.store.meta.activity_count)),
        )
        return uniq

    def run_forever(self) -> None:
        """Watch WATCH_DIR: после паузы без событий — sync_once + publish."""
        if not self.watch_dir.is_dir():
            raise FileNotFoundError(f"WATCH_DIR не существует: {self.watch_dir}")

        handler = _DebouncedSyncHandler(self)
        observer = Observer()
        observer.schedule(handler, str(self.watch_dir), recursive=True)
        observer.start()
        log.info(
            "%s слежу за %s  (пауза %.1fs после события).  %s",
            magenta("👁 watch"),
            cyan(str(self.watch_dir)),
            self.debounce_s,
            dim("Ctrl+C — стоп"),
        )
        try:
            while True:
                time.sleep(1.0)
        finally:
            handler.cancel()
            observer.stop()
            observer.join(timeout=5)

    def _publish(self, dirty: list[Path]) -> None:
        if self.publisher is not None:
            self.publisher(dirty)

    def _load_skipped(self) -> dict[str, str]:
        if not self._skipped_path.exists():
            return {}
        try:
            data = json.loads(self._skipped_path.read_text())
            return {str(k): str(v) for k, v in data.items()}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_skipped(self) -> None:
        self._skipped_path.parent.mkdir(parents=True, exist_ok=True)
        self._skipped_path.write_text(
            json.dumps(self._skipped, indent=2, ensure_ascii=False)
        )


class _DebouncedSyncHandler(FileSystemEventHandler):
    def __init__(self, ingest: LocalFsIngest) -> None:
        super().__init__()
        self.ingest = ingest
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._busy = threading.Lock()

    def cancel(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        paths = [event.src_path]
        dest = getattr(event, "dest_path", None)
        if dest:
            paths.append(dest)
        if not any(str(p).lower().endswith(".fit") for p in paths):
            return
        name = Path(event.src_path).name
        kind_map = {
            "created": (green, "появился"),
            "deleted": (red, "исчез"),
            "modified": (yellow, "изменился"),
            "moved": (cyan, "перемещён"),
        }
        color_fn, kind = kind_map.get(event.event_type, (cyan, event.event_type))
        log.info("%s файл %s: %s", color_fn("●"), kind, _short(name))
        self._schedule()

    def _schedule(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.ingest.debounce_s, self._run_sync)
            self._timer.daemon = True
            self._timer.start()

    def _run_sync(self) -> None:
        if not self._busy.acquire(blocking=False):
            self._schedule()
            return
        try:
            log.info("%s события улеглись → sync + publish…", cyan("…"))
            dirty = self.ingest.sync_once()
            if dirty:
                log.info("%s публикую %s тайлов…", magenta("↑"), bold(str(len(dirty))))
            self.ingest._publish(dirty)
            if dirty:
                log.info(
                    "%s тайлы на Pages обновлены (%s)",
                    green("✓ готово"),
                    cyan(str(len(dirty))),
                )
            else:
                log.info("%s на Pages менять нечего", green("✓ готово"))
        except Exception:
            log.exception("%s sync failed", red("ошибка watch"))
        finally:
            self._busy.release()
