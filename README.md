# bike-tracks-layer

XYZ TileLayer с сетью персональных велотреков для [nakarte.me](https://nakarte.me).

**Статус:** спецификация готова, реализация не начата.

## Идея

1. HealthFit кладёт `.fit` в Dropbox после тренировки.
2. Webhook → сервис обновляет аккумулятор частоты участков.
3. Рендер PNG-тайлов в стиле Komoot personal tracks (чёткие линии, один цвет, alpha от частоты).
4. В nakarte.me слой включается по URL `…/tiles/bike-tracks/{z}/{x}/{y}.png`.

Self-host nakarte не делаем — только пайплайн и тайлы.

## Документация

| Файл | Содержание |
|------|------------|
| [docs/SPEC.md](docs/SPEC.md) | Требования и зафиксированные решения |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Пайплайн, компоненты, контракты |
| [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) | Стек, этапы разработки, чеклисты |

## Быстрый старт (когда появится код)

См. этапы в [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md).
