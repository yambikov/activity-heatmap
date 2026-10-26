"""Цветной дружелюбный лог для терминала."""

from __future__ import annotations

import logging
import sys

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


def setup_logging(verbose: bool) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(FriendlyFormatter())
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for name in ("urllib3", "PIL"):
        logging.getLogger(name).setLevel(logging.WARNING)
