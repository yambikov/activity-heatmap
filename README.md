# bike-tracks-layer

XYZ TileLayer с сетью персональных велотреков для [nakarte.me](https://nakarte.me).

**Статус:** спецификация готова, реализация не начата.

## Идея

1. HealthFit кладёт `.fit` в Dropbox после тренировки.
2. На ПК воркер видит create/delete в папке Dropbox → add/remove в аккумуляторе.
3. Рендер PNG (стиль Komoot personal tracks) → публикация на **GitHub Pages**.
4. В nakarte.me слой по URL Pages. При переносе на VDS меняются адаптеры и URL, не ядро.

Self-host nakarte не делаем.

## Документация

| Файл | Содержание |
|------|------------|
| [docs/SPEC.md](docs/SPEC.md) | Требования и зафиксированные решения |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Пайплайн, компоненты, контракты |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Переносимость ПК ↔ VDS |
| [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) | Стек, этапы разработки, чеклисты |

## Быстрый старт (когда появится код)

См. этапы в [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md).
