# Установка на Mac

Репозиторий собран в облачном агенте. Путь `/Users/yambikov/Desktop/dev/activity-heatmap` на машине агента недоступен — скопируйте архив локально:

```bash
mkdir -p ~/Desktop/dev
cd ~/Desktop/dev
# распаковать activity-heatmap-with-git.tar.gz (с историей git)
tar -xzf /path/to/activity-heatmap-with-git.tar.gz
# или без .git:
# tar -xzf /path/to/activity-heatmap.tar.gz
cd activity-heatmap
git status   # если брали with-git
```

Архивы лежат у агента в `/agent/artifacts/`.
