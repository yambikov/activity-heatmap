# План реализации

## Предлагаемый стек (v1)

| Слой | Вариант |
|------|---------|
| Язык | Python 3.12+ |
| FIT | `fitdecode` (или аналог) |
| Гео / raster | `numpy`, `Pillow`; при необходимости `affine` / mercantile |
| Core | Чистый модуль add/remove/rebuild + state на диске |
| Ingest | Общий: `sync` на старте + Dropbox webhook в рантайме ([OPERATIONS.md](./OPERATIONS.md)) |
| Publish v1 | GitHub Pages (git push dirty tiles) |
| Publish VDS | filesystem + Caddy/nginx (или S3/R2) |
| Упаковка | Один Docker-образ / CLI; профиль через env (см. [DEPLOYMENT.md](./DEPLOYMENT.md)) |

Стек не догма: допустим Go/Node при тех же контрактах. Главное — границы core / ingest / publish.

## Этапы

### Этап 0 — Каркас репозитория

- [ ] Структура проекта (`src/core`, `src/ingest`, `src/publish`, `data/`, `docs/`, `.env.example`)
- [ ] Конфиг: `INGEST_MODE`, `PUBLISH_MODE`, пути, цвет, alpha, z-range
- [ ] CLI-заглушки `add` / `remove` / `rebuild`
- [ ] Интерфейсы адаптеров ingest/publish (без привязки к GitHub/VDS в core)

### Этап 1 — Offline прототип рендера

Без Dropbox: локальная папка с `.fit`.

- [ ] Парсер FIT → polyline
- [ ] Accumulator: visit-mask + `counts += 1` / `counts -= 1`
- [ ] Activity store: сохранение mask по `activity_id` (для offline — имя файла)
- [ ] Рендер PNG тайлов (стиль линий Komoot)
- [ ] Тест: add трек → линия есть; remove → вклад исчез
- [ ] Подбор `alpha_min`, `alpha_max`, `count_ref`, толщины линии

**DoD:** на тестовом наборе треков слой выглядит как сеть путей; редкие дороги читаются; удаление активности откатывает её вклад.

### Этап 2 — Sync + webhook + GitHub Pages (ПК)

- [ ] `activity-heatmap sync` — полный reconcile Dropbox ↔ activities + publish
- [ ] `activity-heatmap agent` — на старте вызывает sync, затем слушает webhook
- [ ] Dropbox webhook (challenge + changes); на ПК — туннель + `PUBLIC_BASE_URL`
- [ ] Lock на `DATA_DIR`
- [ ] Publish `github_pages` (dirty paths)
- [ ] Опционально: `ENABLE_FS_WATCH_FALLBACK` без туннеля

**DoD:**
- агент выключен → `sync` догоняет всё;
- `agent` при старте догоняет, дальше create/delete через webhook обновляют слой.

### Этап 3 — Тот же агент на VDS

- [ ] Publish `filesystem` (и опционально `s3`)
- [ ] `PUBLIC_BASE_URL` = домен VDS (без туннеля)
- [ ] Чеклист [DEPLOYMENT.md](./DEPLOYMENT.md)

**DoD:** смена env + копия `data/state` достаточны; CLI тот же.

### Этап 4 — Усиление

- [ ] `rebuild` из всей папки
- [ ] Расширение bbox на лету
- [ ] Бэкап `data/state`
- [ ] Лог/Telegram: add/remove
- [ ] Опционально: home radius, слои по годам, сжатие bbox

## Структура каталогов (предложение)

```
activity-heatmap/
  docs/
  src/
    core/               # parse, accumulate, render, add/remove/rebuild
    ingest/
      local_fs.py
      dropbox_webhook.py
      sync_once.py
    publish/
      github_pages.py
      filesystem.py
      s3.py
    api/                # только для webhook-режима
  data/
    state/              # activities, counts, bbox (+ cursor в API-режиме)
    tiles/activity-heatmap/  # локальный вывод core перед publish
  docker-compose.yml    # profiles: local | vds
  .env.example
  README.md
```

## Параметры рендера (стартовые, тюнить на этапе 1)

```yaml
color_rgb: [220, 90, 20]   # один цвет; точное значение — на глаз
alpha_min: 0.40
alpha_max: 0.90
count_ref: "p95"           # перцентиль по ненулевым ячейкам
line_width_px: 2.0         # на z_max
z_min: 9
z_max: 15
bbox_margin_m: 2000
```

## Ручная проверка в nakarte.me

1. Открыть nakarte.me.
2. Добавить custom raster layer / тайлы (как принято в UI на момент внедрения).
3. URL: `https://<host>/tiles/activity-heatmap/{z}/{x}/{y}.png`
4. Прозрачность слоя в UI ~100% (alpha уже в PNG); при необходимости чуть снизить.
5. Проверить одиночный выезд и накатанный участок на одном zoom.

## Риски и митигации

| Риск | Митигация |
|------|-----------|
| Dropbox webhook пропущен | Периодический `sync-once` (cron раз в час): догоняет и create, и delete |
| Потерян activity store | Без масок delete невозможен → только `rebuild` из папки; бэкапить `activities` |
| Дом/паузы засвечивают карту | Фильтр стоянок или home radius (этап 5) |
| CDN отдаёт старые тайлы | Короткий TTL / overwrite + короткий max-age |
| Раздувание grid | Bbox только по трекам + margin; не рендерить пустые тайлы вне данных |
| Смена FIT на том же path | Ключ = Dropbox `file_id`; при неясном replace — rebuild |

## Связанные решения (краткий журнал)

1. Слой для nakarte через XYZ, не отдельное приложение карты.
2. Self-host nakarte — **нет** (простой вариант).
3. Источник — **Dropbox** (удобнее webhook, чем Google Drive); HealthFit пишет FIT туда.
4. Визуал — **Komoot-like tracks**, не Strava heat blur.
5. Частота по визитам активностей; редкое видно (`alpha_min`).
6. Обновление — webhook, инкрементальные тайлы.
7. **Delete в Dropbox → вычитание вклада** из слоя; для этого храним visit-mask на каждую активность.
8. **Деплой v1:** ПК + GitHub Pages; перенос на VDS через смену publish/URL, ядро общее ([DEPLOYMENT.md](./DEPLOYMENT.md)).
9. **Агент:** старт/`sync` → полный догон; в рантайме → webhook ([OPERATIONS.md](./OPERATIONS.md)).
