# Архитектура

## Обзор

```
Apple Watch → HealthFit → Dropbox (*.fit)
                              │
                              ▼ webhook (create | delete)
                     Ingest API (VPS)
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
    Download FIT         Activity store       Accumulator
    parse coords         id → visit-mask      (visit counts)
         │                    │                    │
         │     create: mask → counts += 1          │
         │     delete: mask → counts -= 1          │
         └────────────────────┴────────────────────┘
                              │
                              ▼
                       Tile renderer (dirty tiles)
                              │
                              ▼
                    Object storage / CDN
                 /tiles/bike-tracks/{z}/{x}/{y}.png
                              │
                              ▼
                      nakarte.me custom layer
```

Простой вариант: один небольшой сервис на VPS (+ диск или S3-совместимое хранилище). Отдельный Kubernetes / PostGIS / tile server не нужны.

## Компоненты

### 1. Dropbox source

- Папка, например `/HealthFit` или `/BikeTracks`.
- HealthFit: автоэкспорт workout → FIT в эту папку.
- App Dropbox: permissions на чтение папки + webhook на изменения.

**Поток webhook:**

1. Dropbox POST на `https://<host>/hooks/dropbox` (challenge verification при подписке).
2. Сервис читает changes по **cursor** (`files/list_folder/continue` или аналог).
3. Для каждого события по `.fit`:
   - **file present / added** → очередь `add(file_id)`;
   - **file deleted** → очередь `remove(file_id)`.
4. Safety net: периодический `sync-once` сверяет папку Dropbox с activity store (догоняет пропущенные create/delete).

Хранить **Dropbox cursor**, **activity store** (`file_id` → вклад) и глобальный **counts**.

### 2. FIT ingest

- Скачать файл по Dropbox API.
- Распарсить FIT → последовательность lat/lon (record messages с position).
- Отбросить точки без валидных координат.
- Опционально (лёгкий фильтр, не «аналитика»): скорость ≈ 0 / стоянка — не растеризовать, чтобы дом не засвечивался паузами. Если спорно — можно отключить в v1.

Выход шага: polyline активности + `activity_id` (= Dropbox `id`).

### 3. Accumulator (частота визитов) + удаление

Семантика:

- Не `+=` числу GPS-точек.
- Для одной активности строится **visit-mask**: ячейки grid, через которые прошла **линия** маршрута.
- **Add:** `counts[cell] += 1` по mask; mask сохраняется в activity store под `file_id`.
- **Remove:** достать mask по `file_id` → `counts[cell] = max(0, counts[cell] - 1)` → удалить запись из activity store → dirty-тайлы.
- Если `file_id` уже в store при add → no-op. Если при remove записи нет → no-op.

Рекомендуемая модель хранения v1:

- Прямоугольный grid в Web Mercator на `z_max` (например 14 или 15) с динамическим **bbox** = union треков + margin.
- Персист counts: один файл (npz / memmap / SQLite blob / chunk-файлы по тайлам `z_max`).
- Персист вкладов: на каждую активность — сжатый список ячеек (или run-length / roaring bitmap), ключ = Dropbox `file_id`.
- При выходе трека за bbox — расширить grid и перенести данные.
- Сжатие bbox после delete в v1 **не обязательно** (можно оставить пустые края).

Полный rebuild из папки Dropbox — fallback, если state рассинхронизировался; не основной путь для delete.

### 4. Renderer (стиль Komoot tracks)

- Не KDE / Gaussian heatmap.
- На `z_max`: растеризация **полилиний** толщиной ~1.5–2.5 px (в пикселях тайла), anti-alias допустим.
- Цвет: константа `RGB` (например янтарный); alpha из `counts`:

  ```
  t = log1p(count) / log1p(count_ref)
  alpha = alpha_min + (alpha_max - alpha_min) * clamp(t, 0, 1)
  ```

  - `alpha_min` высокий (редкие дороги хорошо видны).
  - `count_ref` — перцентиль (например p90–p95), не глобальный max домашнего круга.
- Тайлы ниже `z_max`: downscale / перерисовка родителей из counts или из дочерних PNG.
- Формат: PNG RGBA, фон полностью прозрачный.
- Схема: XYZ (OSM), `{z}/{x}/{y}.png`.
- Диапазон zoom (старт): `z_min ≈ 8…10`, `z_max ≈ 14…15`.

Dirty set (и для add, и для remove): ячейки из mask активности → тайлы на `z_max` → предки до `z_min` → overwrite только их. Ячейки с `count = 0` дают полностью прозрачный PNG (или удаление тайла, если он стал пустым — на усмотрение реализации).

### 5. Storage & CDN

- Локальный диск VPS за nginx/Caddy **или** R2/S3 + Cloudflare.
- URL стабильный, CORS обычно не критичен для `<img>`/leaflet tiles, но HTTPS обязателен.
- Cache-Control: умеренный TTL + purge/overwrite dirty paths после рендера.

### 6. Клиент (nakarte)

- Пользователь добавляет слой вручную (URL template).
- В v1 слой **не** зашит в форк nakarte (self-host отвергнут как усложнение).

## State, которое нужно персистить

| Ключ | Назначение |
|------|------------|
| `dropbox_cursor` | Инкрементальный опрос изменений |
| `activities` | `file_id` → { path?, processed_at, visit_mask } — нужно для delete |
| `counts` / grid | Аккумулятор визитов |
| `bbox` | Текущий охват grid |
| `render_params` | цвет, alpha_min/max, count_ref, z-range, line width |

## Контракты HTTP (черновик)

```
GET  /healthz
POST /hooks/dropbox          # webhook + challenge
POST /admin/rebuild          # опционально: полная пересборка из всех FIT в папке
GET  /tiles/bike-tracks/{z}/{x}/{y}.png
```

Админ-эндпоинты защитить (token / firewall), webhook — verification Dropbox.

## Безопасность

- Dropbox refresh token / app secret только в env / secret file, не в git.
- Webhook endpoint проверять (подпись/challenge по документации Dropbox).
- Папка Dropbox — только экспорт HealthFit, без лишних файлов.

## Масштаб

Личный объём (сотни–тысячи тренировок, региональный bbox): один VPS 1 vCPU / 1–2 GB RAM достаточно для старта. Полная пересборка — ночной/ручной fallback, не основной путь.
