#!/usr/bin/env python3
"""Локальная раздача тайлов с CORS (для превью / туннеля → nakarte)."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class CORSHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:
        # тише: только ошибки / не-тайлы
        msg = fmt % args
        if " 200 " in msg and ".png" in msg:
            return
        super().log_message(fmt, *args)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "tiles",
    )
    args = ap.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"нет каталога тайлов: {root}")

    handler = partial(CORSHandler, directory=str(root))
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"tiles root: {root}")
    print(f"local:      http://127.0.0.1:{args.port}/activity-heatmap/{{z}}/{{x}}/{{y}}.png")
    print("для nakarte нужен HTTPS-туннель на этот порт")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
