# План реализации

## Предлагаемый стек (v1)

| Слой | Вариант |
|------|---------|
| Язык | Python 3.12+ |
| FIT | `fitdecode` (или аналог) |
| Гео / raster | `numpy`, `Pillow`; при необходимости `affine` / mercantile |
| Web | FastAPI (webhook + health + раздача/прокси тайлов) |
| Очередь | Внутрипроцессная / `asyncio` queue; при росте — RQ/Redis |
| Dropbox | Official Dropbox HTTP API + webhook |
| Процесс-менеджер | systemd или Docker Compose на VPS |
| HTTP/TLS | Caddy или nginx |
| Тайлы | Диск `./data/tiles/...` или R2/S3 |

Стек не догма: допустим Go/Node при тех же контрактах.

## Этапы

### Этап 0 — Каркас репозитория

- [ ] Структура проекта (`src/`, `data/`, `docs/`, `.env.example`)
- [ ] Конфиг: Dropbox path, цвет, alpha, z-range, tile root
- [ ] `GET /healthz`

### Этап 1 — Offline прототип рендера

Без Dropbox: локальная папка с `.fit`.

- [ ] Парсер FIT → polyline
- [ ] Accumulator visit-mask + counts
- [ ] Рендер PNG тайлов (стиль линий Komoot)
- [ ] Визуальная проверка в nakarte / QGIS / leaflet sandbox
- [ ] Подбор `alpha_min`, `alpha_max`, `count_ref`, толщины линии

**DoD:** на тестовом наборе треков слой выглядит как сеть путей; редкие дороги читаются.

### Этап 2 — Dropbox sync (pull)

- [ ] OAuth / refresh token
- [ ] Список файлов в папке, скачивание `.fit`
- [ ] `processed_files` + идемпотентность
- [ ] CLI: `sync-once`

**DoD:** повторный sync не меняет counts.

### Этап 3 — Webhook

- [ ] Регистрация webhook Dropbox
- [ ] Challenge + обработка notification
- [ ] Cursor-based changes
- [ ] Инкрементальный dirty-tile update + upload/overwrite

**DoD:** положили новый FIT в Dropbox → в nakarte после refresh тайлов виден новый след (с учётом CDN cache).

### Этап 4 — Деплой

- [ ] VPS: Docker Compose или systemd
- [ ] HTTPS, домен, путь `/tiles/bike-tracks/...`
- [ ] Бэкап `counts` + `processed_files`
- [ ] Инструкция для пользователя: как добавить слой в nakarte.me

### Этап 5 — Усиление (после v1)

- [ ] `POST /admin/rebuild` из всей папки Dropbox
- [ ] Расширение bbox на лету
- [ ] Метрики/лог в Telegram: «обработан файл X, N тайлов»
- [ ] Опционально: исключить радиус дома
- [ ] Опционально: отдельные слои по годам

## Структура каталогов (предложение)

```
bike-tracks-layer/
  docs/                 # эта документация
  src/
    dropbox_/           # client, webhook
    fit/                # parse
    accumulate/         # counts grid
    render/             # tiles
    api/                # FastAPI app
  data/
    state/              # cursor, processed, counts, bbox
    tiles/bike-tracks/  # {z}/{x}/{y}.png
  scripts/
    sync_once.py
    rebuild.py
  docker-compose.yml
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
3. URL: `https://<host>/tiles/bike-tracks/{z}/{x}/{y}.png`
4. Прозрачность слоя в UI ~100% (alpha уже в PNG); при необходимости чуть снизить.
5. Проверить одиночный выезд и накатанный участок на одном zoom.

## Риски и митигации

| Риск | Митигация |
|------|-----------|
| Dropbox webhook пропущен | Периодический `sync-once` (cron раз в час) как safety net |
| Дом/паузы засвечивают карту | Фильтр стоянок или home radius (этап 5) |
| CDN отдаёт старые тайлы | Короткий TTL или cache bust query (хуже для nakarte) / overwrite + короткий max-age |
| Раздувание grid | Bbox только по трекам + margin; не рендерить пустые тайлы вне данных |
| Смена FIT на тот же path | v1: ключ = Dropbox file id; replace без пересчёта — принять или делать rebuild |

## Связанные решения (краткий журнал)

1. Слой для nakarte через XYZ, не отдельное приложение карты.
2. Self-host nakarte — **нет** (простой вариант).
3. Источник — **Dropbox** (удобнее webhook, чем Google Drive); HealthFit пишет FIT туда.
4. Визуал — **Komoot-like tracks**, не Strava heat blur.
5. Частота по визитам активностей; редкое видно (`alpha_min`).
6. Обновление — webhook, инкрементальные тайлы.
