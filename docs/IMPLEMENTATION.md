# План реализации

## Предлагаемый стек (v1)

| Слой | Вариант |
|------|---------|
| Язык | Python 3.12+ |
| FIT | `fitdecode` (или аналог) |
| Гео / raster | `numpy`, `Pillow`; при необходимости `affine` / mercantile |
| Core | Чистый модуль add/remove/rebuild + state на диске |
| Ingest v1 | `sync` на старте + **FS watch** папки Dropbox Desktop ([OPERATIONS.md](./OPERATIONS.md)) |
| Publish v1 | GitHub Pages (git push dirty tiles) |
| Publish VDS | filesystem + Caddy/nginx (или S3/R2) |
| Упаковка | Один Docker-образ / CLI; профиль через env (см. [DEPLOYMENT.md](./DEPLOYMENT.md)) |

Стек не догма: допустим Go/Node при тех же контрактах. Главное — границы core / ingest / publish.

## Этапы

### Этап 0 — Каркас репозитория

- [x] Структура проекта (`src/activity_heatmap/{core,ingest,publish,api}`, `data/`, `docs/`, `.env.example`)
- [x] Конфиг: `INGEST_MODE`, `PUBLISH_MODE`, пути, цвет, alpha, z-range
- [x] CLI-заглушки `sync` / `agent` / `add` / `remove` / `rebuild`
- [x] Интерфейсы адаптеров ingest/publish (без привязки к GitHub/VDS в core)

### Этап 1 — Offline прототип рендера

Без Dropbox: локальная папка с `.fit`.

- [x] Парсер FIT → polyline (`fitdecode`, фильтр Virtual/Indoor/non-bike)
- [x] Accumulator: visit-mask + `counts += 1` / `counts -= 1`
- [x] Activity store: mask по `activity_id` = sha256 файла
- [x] Рендер PNG тайлов (стиль линий Komoot)
- [x] Тест: add трек → линия есть; remove → вклад исчез
- [ ] Подбор `alpha_min`, `alpha_max`, `count_ref`, толщины линии (на глаз в nakarte)

**DoD:** на тестовом наборе треков слой выглядит как сеть путей; редкие дороги читаются; удаление активности откатывает её вклад.  
Проверка 2026-10-25: `rebuild` → **97** велотреков из HealthFitExporter, **3574** PNG.

### Этап 2 — Sync + FS watch + GitHub Pages (ПК)

- [x] `activity-heatmap sync` — reconcile `WATCH_DIR` ↔ activities + publish
- [x] `activity-heatmap agent` — sync на старте, затем FS watch (debounce)
- [x] Lock на `DATA_DIR`
- [x] Publish `github_pages` (dirty paths + `PAGES_SECRET_PATH` + CLI `publish`)
- [x] Без туннеля и без Dropbox webhook

**DoD:**
- агент выключен → `sync` догоняет всё;
- `agent` при старте догоняет, дальше create/delete в папке обновляют слой.

### Этап 3 — Адаптер webhook для VDS (позже)

- [ ] Dropbox webhook + `PUBLIC_BASE_URL`
- [ ] Publish `filesystem` (и опционально `s3`)
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
3. URL: `https://<host>/<PAGES_SECRET_PATH>/activity-heatmap/{z}/{x}/{y}.png`
4. Прозрачность слоя в UI ~100% (alpha уже в PNG); при необходимости чуть снизить.
5. Проверить одиночный выезд и накатанный участок на одном zoom.

## Риски и митигации

| Риск | Митигация |
|------|-----------|
| Пропущен watch (агент выключен) | При следующем старте / `sync` — полный догон |
| Клиент Dropbox не синкнул файл | Пользователь открывает ПК/Dropbox; затем sync/agent |
| Потерян activity store | Без масок delete невозможен → `rebuild`; бэкапить `activities` |
| Дом/паузы засвечивают карту | Фильтр стоянок или home radius (позже) |
| Pages/git раздувается | Не коммитить пустые тайлы; ограничить z_max / bbox |
| Смена FIT на том же path | Ключ = content hash; при сомнении — rebuild |

## Связанные решения (краткий журнал)

1. Слой для nakarte через XYZ, не отдельное приложение карты.
2. Self-host nakarte — **нет**.
3. Источник — **HealthFit → Dropbox** (не Google Drive).
4. Визуал — **Komoot-like tracks**, не Strava heat blur.
5. Частота по визитам активностей; редкое видно (`alpha_min`).
6. **Delete** → вычитание вклада (visit-mask на активность).
7. Деплой v1: **ПК + GitHub Pages**; ядро переносимо на VDS.
8. Агент: старт/`sync` → полный догон; в рантайме → **FS watch** (не webhook на ПК).
9. Heatmap UI HealthFit не экспортируем — только FIT.
