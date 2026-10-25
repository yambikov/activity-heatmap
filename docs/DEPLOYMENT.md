# Деплой и переносимость (ПК → VDS)

Цель: считать и публиковать **одинаковым ядром**; меняются только **адаптеры** (как узнаём про файлы и куда кладём тайлы) и конфиг.

## Принцип: три слоя

```
┌─────────────────────────────────────────────────────────┐
│  Ingest adapter                                          │
│  sync-once + local_fs_watch (v1)                         │
└──────────────────────────┬──────────────────────────────┘
                           │  команды ядра:
                           │  add(fit_bytes, file_id)
                           │  remove(file_id)
                           │  rebuild()
┌──────────────────────────▼──────────────────────────────┐
│  Core (без привязки к хосту)                             │
│  parse FIT → visit-mask → counts ±1 → render dirty PNG   │
│  state: data/state/  (activities, counts, bbox)          │
│  tiles out: data/tiles/activity-heatmap/{z}/{x}/{y}.png  │
└──────────────────────────┬──────────────────────────────┘
                           │  publish(changed_paths)
┌──────────────────────────▼──────────────────────────────┐
│  Publish adapter                                         │
│  github_pages | filesystem (nginx/caddy)                 │
└─────────────────────────────────────────────────────────┘
```

Ядро **никогда** не знает про GitHub, VDS или webhook. Только про локальные `data/state` и `data/tiles`.

## Профили запуска

Один CLI, разные `.env`.

### Профиль A — ПК + GitHub Pages (старт)

| Роль | Реализация |
|------|------------|
| Ingest | На **старте** — `sync-once`; пока работает — **FS watch** папки Dropbox Desktop (без туннеля; см. [OPERATIONS.md](./OPERATIONS.md)) |
| Core | тот же |
| Publish | `github_pages`: commit/push dirty tiles в ветку `gh-pages` под `PAGES_SECRET_PATH` |
| URL в nakarte | `https://<user>.github.io/<repo>/<PAGES_SECRET_PATH>/activity-heatmap/{z}/{x}/{y}.png` |
| Когда онлайн | ПК/агент нужен, чтобы обработать новую тренировку; Pages отдаёт уже залитое всегда |

**Защита URL:** длинный `PAGES_SECRET_PATH` — obscurity (случайный человек не угадает). Это **не** логин. В публичном репо сегмент виден в дереве `gh-pages`; не светите репо в профиле и не шарьте ссылку.

### Профиль B — VDS (перенос)

| Роль | Реализация |
|------|------------|
| Ingest | тот же `local_fs` (или свой адаптер позже) |
| Core | **тот же** код и тот же формат `data/state` |
| Publish | `filesystem` — тайлы на диске, раздаёт Caddy/nginx |
| URL в nakarte | `https://tiles.example.com/tiles/activity-heatmap/{z}/{x}/{y}.png` |
| Когда онлайн | VDS always-on |

## Конфиг (контракт)

Минимальный набор переменных — чтобы переезд = смена env, не рефакторинг:

```bash
PUBLISH_MODE=github_pages|filesystem

# общее
DATA_DIR=./data
TILE_URL_PREFIX=https://…/<PAGES_SECRET_PATH>/activity-heatmap

# v1 ПК — обязательно
WATCH_DIR=/path/to/Dropbox/HealthFit

# github_pages
GITHUB_PAGES_REPO=owner/repo
GITHUB_PAGES_BRANCH=gh-pages
GITHUB_TOKEN=          # опционально; иначе SSH
PAGES_SECRET_PATH=…   # python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Что должно быть идентично на ПК и VDS

1. Формат **state** (`activities` + `counts` + `bbox`) — переносится копированием каталога.
2. Имена тайлов `{z}/{x}/{y}.png` и параметры рендера.
3. CLI:
   - `activity-heatmap sync` — полный догон, выход
   - `activity-heatmap agent` — sync на старте, затем FS watch
   - `activity-heatmap rebuild` — полная пересборка
4. Тот же репо/CLI: ПК `PUBLISH_MODE=github_pages` + `WATCH_DIR`; VDS `PUBLISH_MODE=filesystem`. Core общий.

## Чеклист переноса ПК → VDS

1. Поднять VDS, поставить тот же образ/репо.
2. Скопировать `data/state/` (обязательно) и при желании уже готовые `data/tiles/`.
3. Выставить `PUBLISH_MODE=filesystem` (и при необходимости другой ingest).
4. Настроить Caddy/nginx на `data/tiles`.
5. В nakarte **сменить только URL** слоя на новый хост.
6. На ПК остановить watch/publish (чтобы два воркера не дрались за один state) **или** сделать ПК read-only архивом.

Пока state один «владелец»-воркер — конфликтов нет. Два активных пайплайна на одни counts без синхронизации — нельзя.

## Антипаттерны (ломают простой перенос)

- Логика «сразу git commit» внутри рендерера — только в publish-адаптере.
- State в git вместе с тайлами Pages — на VDS будет мешать; state всегда в `data/state`, локально / на диске VDS / бэкап отдельно.
- Жёстко прошитый URL GitHub Pages в коде — только конфиг / README для пользователя.
- Webhook-only без `sync-once` — на VDS ок как primary, но CLI sync должен работать везде (и как safety net, и для отладки на ПК).

## Рекомендуемый путь продукта

1. **v1:** профиль A (ПК + GitHub Pages).
2. При росте объёма / желании «обновлять без включённого ПК» → профиль B, без переписывания ядра.
