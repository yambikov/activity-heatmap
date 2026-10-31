"""Цветной лог в терминал + опциональная запись в файл."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import click


def _tty() -> bool:
    return sys.stderr.isatty()


def style(text: str, **kwargs) -> str:
    if not _tty():
        return text
    return click.style(text, **kwargs)


def dim(text: str) -> str:
    return style(text, fg="bright_black")


def cyan(text: str) -> str:
    return style(text, fg="cyan")


def green(text: str) -> str:
    return style(text, fg="green", bold=True)


def red(text: str) -> str:
    return style(text, fg="red", bold=True)


def yellow(text: str) -> str:
    return style(text, fg="yellow")


def magenta(text: str) -> str:
    return style(text, fg="magenta", bold=True)


def bold(text: str) -> str:
    return style(text, bold=True)


class FriendlyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        t = self.formatTime(record, "%H:%M:%S")
        msg = record.getMessage()
        if record.levelno >= logging.ERROR:
            mark = style("✖", fg="red", bold=True)
        elif record.levelno >= logging.WARNING:
            mark = style("!", fg="yellow", bold=True)
        elif record.levelno == logging.DEBUG:
            mark = dim("·")
        else:
            mark = style("›", fg="cyan")
        return f"{dim(t)} {mark} {msg}"


class PlainFormatter(logging.Formatter):
    """Без ANSI — для файла."""

    def format(self, record: logging.LogRecord) -> str:
        t = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        level = record.levelname[0]  # I/W/E/D
        name = record.name.removeprefix("activity_heatmap.")
        return f"{t} {level} {name}: {record.getMessage()}"


def setup_logging(verbose: bool, log_file: str | Path | None = None) -> Path | None:
    """Консоль всегда; файл — если передан путь или LOG_FILE в env."""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(FriendlyFormatter())
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    root.addHandler(console)

    path: Path | None = None
    raw = (str(log_file).strip() if log_file else "") or os.getenv("LOG_FILE", "").strip()
    if raw:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(PlainFormatter())
        file_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        root.addHandler(file_handler)
        logging.getLogger(__name__).info("лог-файл: %s", path)

    for name in ("urllib3", "PIL"):
        logging.getLogger(name).setLevel(logging.WARNING)
    return path
