# Режим работы агента (вариант 1 — ПК)

## Жизненный цикл (зафиксировано)

```
агент выключен ──(старт)──► sync-once (полный догон) ──► FS watch папки Dropbox
                                    ▲
команда sync / одноразовый запуск ──┘

уже работает ──► только watch папки (инкремент create/delete)
```

| Состояние | Поведение |
|-----------|-----------|
| **Старт агента** (`activity-heatmap agent`) | Сначала обязательный **`sync-once`**: сверить локальную папку Dropbox Desktop с `activities`, add/remove, опубликовать dirty-тайлы. Затем включить **filesystem watch**. |
| **Уже работает** | **Watch папки** Dropbox Desktop → инкрементальный add/remove + publish. Полный перескан на каждое событие не гонять. |
| **Агент выключен** | Слой на GitHub Pages не обновляется. Пропущенные FIT догонятся при следующем старте / `sync`. |
| **Разовая команда** | `activity-heatmap sync` = тот же `sync-once` + publish, выход. |

Идемпотентность: повторный `sync-once` при актуальном state ничего не меняет.

## Почему не Dropbox webhook на ПК (v1)

Webhook Dropbox требует публичный HTTPS (туннель). Для автономии на домашнем ПК **не используем туннель**.

Вместо этого:

```
HealthFit → Dropbox cloud → клиент Dropbox Desktop → локальная папка
                                                      │
                                                      ▼ FS watch / sync
                                                 ваш агент
```

Туннель и Dropbox webhook — опция для **профиля VDS** позже (см. [DEPLOYMENT.md](./DEPLOYMENT.md)).

## CLI

Пошаговый запуск и примеры лога (файл появился / удалён / тайлы пересчитаны): **[RUN.md](./RUN.md)**.

```bash
activity-heatmap sync          # одноразовый полный догон + publish, выход
activity-heatmap agent         # sync-once на старте, затем FS watch до остановки
activity-heatmap rebuild       # полная пересборка из всех FIT (редко, руками)
```

Блокировка: `data/state/.lock` — нельзя параллельно `sync` и `agent` на один `DATA_DIR`.

Лог по умолчанию INFO: имя `.fit`, add/remove, число пересчитанных тайлов, push на Pages. Ещё подробнее: `activity-heatmap -v agent`.

## Конфиг watch

```bash
WATCH_DIR=/path/to/Dropbox/HealthFit   # папка, куда HealthFit кладёт .fit
```

Стабильный ключ активности: предпочтительно content hash или Dropbox file id (если доступен через API); path+mtime — хуже при rename. Зафиксировать один способ в реализации.

Опционально редкий polling API Dropbox как safety net — не обязателен в v1, если клиент Desktop надёжно синхронизирует папку.

## Минимальное участие человека

- Разово: HealthFit→папка Dropbox, клиент Dropbox на ПК, токен GitHub Pages, URL в nakarte, при желании автозапуск `agent`.
- Дальше:
  - агент включён → после синка файла в папку слой обновится сам;
  - агент выключен → `activity-heatmap sync` или снова запустить `agent` (догонит на старте).
