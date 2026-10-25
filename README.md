# activity-heatmap

XYZ TileLayer с сетью персональных велотреков для [nakarte.me](https://nakarte.me).

**Статус:** спецификация готова, реализация не начата.

## Идея

1. HealthFit кладёт `.fit` в Dropbox после тренировки.
2. На ПК: **`bike-tracks sync` / старт агента** — полный догон; пока агент работает — **Dropbox webhook**.
3. Рендер PNG (стиль Komoot) → **GitHub Pages**.
4. nakarte.me по URL Pages; перенос на VDS — тот же агент, другой publish/URL.

Подробнее: [docs/OPERATIONS.md](docs/OPERATIONS.md).

Self-host nakarte не делаем.

## Документация

| Файл | Содержание |
|------|------------|
| [docs/SPEC.md](docs/SPEC.md) | Требования и зафиксированные решения |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Пайплайн, компоненты, контракты |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Переносимость ПК ↔ VDS |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Режим агента: sync на старте, webhook в рантайме |
| [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) | Стек, этапы разработки, чеклисты |

## Быстрый старт (когда появится код)

См. этапы в [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md).
