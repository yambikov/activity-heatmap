"""Ingest v1: локальная папка Dropbox Desktop (WATCH_DIR)."""

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

log = logging.getLogger(__name__)

PublishFn = Callable[[list[Path]], None]


def _is_transient_skip(reason: str) -> bool:
    r = reason.lower()
    return "too few gps" in r or "no usable gps" in r or "empty mask" in r


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
            log.warning("WATCH_DIR не существует: %s", self.watch_dir)
            return []
        return sorted(
            p
            for p in self.watch_dir.rglob("*")
            if p.is_file() and p.suffix.lower() == ".fit"
        )

    def sync_once(self) -> list[Path]:
        """Сверить WATCH_DIR ↔ activities: add новые, remove исчезнувшие."""
        fits = self.list_fit_files()
        log.info("sync-once: %d .fit в %s", len(fits), self.watch_dir)

        present: dict[str, Path] = {}
        for path in fits:
            try:
                aid = activity_id_for_file(path)
            except OSError as e:
                log.warning("не прочитать %s: %s", path.name, e)
                continue
            present[aid] = path

        dirty: list[Path] = []
        added = removed = skipped = 0

        # remove: в state есть, файла с таким hash больше нет
        for aid in list(self.pipeline.store.index.keys()):
            if aid in present:
                continue
            result = self.pipeline.remove(aid)
            if result.removed:
                removed += 1
                dirty.extend(result.dirty_tiles)
                self._skipped.pop(aid, None)

        # add: файл есть, в state нет (и не в known-skipped)
        for aid, path in present.items():
            if self.pipeline.store.has_activity(aid):
                continue
            if aid in self._skipped:
                skipped += 1
                continue
            result = self.pipeline.add(path, aid)
            if result.added:
                added += 1
                dirty.extend(result.dirty_tiles)
                self._skipped.pop(aid, None)
            else:
                reason = result.reason or "skipped"
                # Dropbox часто сначала кладёт недокачанный .fit (0 GPS) —
                # такой skip не персистим, иначе полный файл с тем же hash не догонится.
                if _is_transient_skip(reason):
                    log.info("пока skip (повторим): %s — %s", path.name, reason)
                else:
                    self._skipped[aid] = f"{path.name}: {reason}"
                skipped += 1

        self._save_skipped()
        # уникальные dirty paths (порядок не важен)
        uniq = list(dict.fromkeys(dirty))
        log.info(
            "sync-once: +%d −%d skip=%d dirty_tiles=%d activities=%d",
            added,
            removed,
            skipped,
            len(uniq),
            self.pipeline.store.meta.activity_count,
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
            "FS watch: %s (debounce=%.1fs). Ctrl+C — стоп.",
            self.watch_dir,
            self.debounce_s,
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
        log.debug("watch event %s %s", event.event_type, event.src_path)
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
            # уже идёт sync — перенести ещё раз
            self._schedule()
            return
        try:
            dirty = self.ingest.sync_once()
            self.ingest._publish(dirty)
            if dirty:
                log.info("watch: опубликовано dirty=%d", len(dirty))
        except Exception:
            log.exception("watch: sync failed")
        finally:
            self._busy.release()
