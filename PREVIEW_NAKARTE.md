# Превью

## Локально (всегда, без туннеля)

http://127.0.0.1:8080/preview.html?v=2

## GitHub Pages (после `activity-heatmap publish`)

Шаблон XYZ (значение уже в `.env` → `TILE_URL_PREFIX`):

```
{TILE_URL_PREFIX}/{z}/{x}/{y}.png
```

Пример:

```
https://yambikov.github.io/activity-heatmap/<PAGES_SECRET_PATH>/activity-heatmap/{z}/{x}/{y}.png
```

Секретный сегмент — только в `.env`, не коммитьте и не светите в публичных чатах.
