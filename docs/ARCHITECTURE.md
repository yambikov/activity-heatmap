# Архитектура

## Обзор

```
Apple Watch → HealthFit → Dropbox (*.fit)
                              │
                              ▼ webhook
                     Ingest API (VPS)
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         Download FIT    State store     Accumulator
         parse coords    (processed ids)  (visit counts)
                              │
                              ▼
                       Tile renderer
                       (line + alpha)
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
2. Сервис делает `list_folder/continue` / получает entries по cursor.
3. Для каждого нового `.fit`: поставить в очередь обработки (или обработать синхронно, если объём мал).

Хранить **Dropbox cursor** и множество **processed file id** (и опционально content hash).

### 2. FIT ingest

- Скачать файл по Dropbox API.
- Распарсить FIT → последовательность lat/lon (record messages с position).
- Отбросить точки без валидных координат.
- Опционально (лёгкий фильтр, не «аналитика»): скорость ≈ 0 / стоянка — не растеризовать, чтобы дом не засвечивался паузами. Если спорно — можно отключить в v1.

Выход шага: polyline активности + `activity_id` (= Dropbox `id`).

### 3. Accumulator (частота визитов)

Семантика как договорённая:

- Не `+=` числу GPS-точек.
- Для одной активности строится **visit-mask**: ячейки grid, через которые прошла **линия** маршрута.
- В глобальный аккумулятор: `counts[cell] += 1` один раз за активность.

Рекомендуемая модель хранения v1:

- Прямоугольный grid в Web Mercator на `z_max` (например 14 или 15) с динамическим **bbox** = union треков + margin.
- Персист: один файл (npz / memmap / SQLite blob / набор chunk-файлов по тайлам `z_max`).
- При выходе трека за bbox — расширить grid и перенести данные.

Альтернатива позже: хранить counts сразу чанками `{z_max}/{x}/{y}.counts` — проще шардировать, сложнее первая реализация.

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

Dirty set: ячейки, изменённые текущей активностью → тайлы на `z_max` → все предки до `z_min` → upload только их.

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
| `processed_files` | id → metadata (path, hash, processed_at) |
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
