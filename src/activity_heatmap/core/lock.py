"""Файловый lock на DATA_DIR — нельзя параллельно sync и agent."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class LockError(RuntimeError):
    pass


@contextmanager
def data_lock(lock_path: Path, *, stale_seconds: float = 86400) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd: int | None = None
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.write(fd, f"{os.getpid()}\n{time.time()}\n".encode())
        yield
    except FileExistsError:
        if _is_stale(lock_path, stale_seconds):
            lock_path.unlink(missing_ok=True)
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.write(fd, f"{os.getpid()}\n{time.time()}\n".encode())
            yield
        else:
            raise LockError(
                f"DATA_DIR занят ({lock_path}). Дождитесь окончания sync/agent "
                "или удалите .lock, если процесс мёртв."
            ) from None
    finally:
        if fd is not None:
            os.close(fd)
            lock_path.unlink(missing_ok=True)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # процесс есть, но чужой — считаем живым
        return True
    return True


def _is_stale(lock_path: Path, stale_seconds: float) -> bool:
    try:
        text = lock_path.read_text().strip().splitlines()
        if len(text) < 2:
            return True
        pid = int(text[0])
        if not _pid_alive(pid):
            return True
        age = time.time() - float(text[1])
        return age > stale_seconds
    except (OSError, ValueError):
        return True
