# Саммари диалога — activity-heatmap

Краткая выжимка договорённостей для переноса в новый чат / папку проекта.  
Дата фиксации: 2026-10-25 (Europe/Moscow).

## Цель продукта

XYZ TileLayer персональных веломаршрутов для **публичного nakarte.me** (custom layer по URL тайлов).  
Self-host nakarte — **нет**.

## Визуал и семантика

| Решение | Выбор |
|---------|--------|
| Стиль | Сеть линий как **Komoot personal tracks**, не размытый Strava heatmap |
| Цвет | Один; меняется только alpha (опционально чуть толщина на частых) |
| Частота | Визит **тренировки** в ячейку (`counts += 1` за активность), не число GPS-точек |
| Редкие дороги | Хорошо видны (`alpha_min` высокий) |
| Delete | Удалили `.fit` → вычесть вклад (хранить visit-mask на активность) |

## Данные и триггеры

| Решение | Выбор |
|---------|--------|
| Источник | **HealthFit → Dropbox** (`.fit`, без лишней аналитики) |
| Не Google Drive | Dropbox удобнее для автоматизации |
| Heatmap из UI HealthFit | Не забираем; только FIT → свой слой |

## Деплой v1

| Решение | Выбор |
|---------|--------|
| Счёт | На **ПК** |
| Отдача тайлов | **GitHub Pages** |
| Автономия | Вариант 1: агент на ПК (может быть выключен) |

## Режим агента (зафиксировано)

```
старт / команда sync  →  полный sync-once (догон)
агент уже работает    →  FS watch папки Dropbox Desktop
туннель / webhook     →  НЕ в v1 на ПК; оставить для будущего VDS
```

CLI: `activity-heatmap sync` | `agent` | `rebuild`.

## Переносимость на VDS

Архитектура: **core** + сменные **ingest/publish**.

- v1 ingest: sync-on-start + FS watch  
- VDS позже: sync-on-start + Dropbox webhook, publish filesystem/S3  
- Перенос: скопировать `data/state`, сменить env/URL в nakarte  

См. [DEPLOYMENT.md](./DEPLOYMENT.md).

## Инфра (ориентиры)

- VDS если понадобится: ~1 vCPU / 2 GB / 40 GB SSD  
- v1 VDS не обязателен  
- HealthFit heatmap API нет — только экспорт FIT/GPX в облако

## Документы в репо

| Файл | Зачем |
|------|--------|
| [SPEC.md](./SPEC.md) | Требования |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Пайплайн и state |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | ПК ↔ VDS |
| [OPERATIONS.md](./OPERATIONS.md) | sync + FS watch |
| [IMPLEMENTATION.md](./IMPLEMENTATION.md) | Этапы кода |
| Этот файл | Контекст диалога для нового чата |

## Статус

Спецификация согласована. Код не начат.  
Локальный git в облаке: `/agent/activity-heatmap`.  
Целевой путь на Mac пользователя: `/Users/yambikov/Desktop/dev/activity-heatmap` (создать локально / из архива — облачный агент к Desktop Mac не писал).

## Что сказать новому агенту (промпт-затравка)

> Реализуй `activity-heatmap` по docs/ в этом репо. v1: ПК, HealthFit→Dropbox→FS watch, sync на старте агента, publish на GitHub Pages, стиль Komoot-линий, delete через visit-mask, слой для nakarte.me. Не self-host nakarte. Не webhook/туннель на ПК. Детали — SPEC, ARCHITECTURE, OPERATIONS, DEPLOYMENT, IMPLEMENTATION, DIALOGUE_SUMMARY.
