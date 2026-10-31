#!/bin/zsh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_SRC="$ROOT/dist/Activity Heatmap.app"
if [[ ! -d "$APP_SRC" ]]; then
  echo "Нет $APP_SRC — пересобери ярлык (см. чат / scripts)."
  exit 1
fi
cp -R "$APP_SRC" "$HOME/Desktop/Activity Heatmap.app"
mkdir -p "$HOME/Applications"
cp -R "$APP_SRC" "$HOME/Applications/Activity Heatmap.app"
cp "$ROOT/scripts/Activity Heatmap.command" "$HOME/Desktop/Activity Heatmap.command"
chmod +x "$HOME/Desktop/Activity Heatmap.command"
echo "Готово: Desktop + ~/Applications"
