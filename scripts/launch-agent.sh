#!/bin/zsh
# Запуск activity-heatmap agent (вызывается из .app / .command).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -x "$ROOT/.venv/bin/activity-heatmap" ]]; then
  echo "Нет .venv. Один раз:"
  echo "  cd \"$ROOT\" && python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
  read -k 1 "?Enter — закрыть "
  exit 1
fi

# убрать протухший lock от мёртвого процесса
LOCK="$ROOT/data/state/.lock"
if [[ -f "$LOCK" ]]; then
  pid="$(head -1 "$LOCK" 2>/dev/null || true)"
  if [[ -n "${pid:-}" ]] && ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$LOCK"
  fi
fi

export PATH="$ROOT/.venv/bin:$PATH"
exec "$ROOT/.venv/bin/activity-heatmap" agent
