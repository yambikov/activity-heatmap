# Установка на Mac

Целевой путь: `/Users/yambikov/Desktop/dev/activity-heatmap`

Облачный агент этот путь не видит. Скопируйте архив и распакуйте:

```bash
mkdir -p ~/Desktop/dev
cd ~/Desktop/dev
tar -xzf /path/to/activity-heatmap-with-git.tar.gz
cd activity-heatmap
git log --oneline | head
```

Архивы: `/agent/artifacts/activity-heatmap-with-git.tar.gz` (с историей) или `activity-heatmap.tar.gz` (без `.git`).

Для нового чата начните с [docs/DIALOGUE_SUMMARY.md](docs/DIALOGUE_SUMMARY.md).
