# activity-heatmap

XYZ TileLayer с сетью персональных велотреков для [nakarte.me](https://nakarte.me).

**Статус:** этапы 0–2 + publish GitHub Pages (секретный сегмент пути).

## Идея

1. HealthFit кладёт `.fit` в Dropbox после тренировки.
2. На ПК: **`sync` / старт агента** — полный догон; пока работает — **watch папки Dropbox Desktop**.
3. Рендер PNG (стиль Komoot) → **GitHub Pages**.
4. nakarte.me по URL Pages; перенос на VDS — тот же core, другой ingest/publish.

Self-host nakarte не делаем. Webhook/туннель на ПК в v1 не нужны.

## Установка (dev)

```bash
cd activity-heatmap
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # поправьте WATCH_DIR и publish
```

## CLI

```bash
activity-heatmap --help
activity-heatmap sync          # догон Dropbox-папки + publish
activity-heatmap agent         # sync на старте, затем FS watch (Ctrl+C)
activity-heatmap rebuild       # полная пересборка
activity-heatmap rerender      # только перерисовать тайлы
activity-heatmap publish       # залить все тайлы на Pages (первый деплой)
activity-heatmap add PATH.fit  # вручную один файл
activity-heatmap remove ID     # вручную вычесть вклад
```

## GitHub Pages (секретный URL)

1. В `.env`: `PUBLISH_MODE=github_pages`, `GITHUB_PAGES_REPO=owner/repo`,
   `PAGES_SECRET_PATH` (длинный токен), `TILE_URL_PREFIX=https://owner.github.io/repo/<token>/activity-heatmap`.
2. Создать **публичный** репо на GitHub (бесплатные Pages), Settings → Pages → branch `gh-pages` / root.
3. `activity-heatmap publish` — первый push всех PNG.
4. В nakarte: `TILE_URL_PREFIX/{z}/{x}/{y}.png`.

Секретный путь скрывает URL от случайных людей; в дереве публичного репо сегмент всё равно виден.

## Документация

| Файл | Содержание |
|------|------------|
| [docs/SPEC.md](docs/SPEC.md) | Требования и зафиксированные решения |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Пайплайн, компоненты, контракты |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Переносимость ПК ↔ VDS |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Sync на старте + FS watch |
| [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) | Стек, этапы разработки, чеклисты |
