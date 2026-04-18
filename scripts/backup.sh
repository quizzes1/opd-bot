#!/usr/bin/env bash
# Дневной бэкап: Postgres-дамп + файлы кандидатов.
# Запускать через cron. Пример: 0 3 * * * /path/to/opd-bot/scripts/backup.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE="$(date +%Y%m%d)"
DEST="$ROOT_DIR/backups/$DATE"
mkdir -p "$DEST"

cd "$ROOT_DIR"

# Postgres (если поднят через docker-compose)
if docker compose ps postgres >/dev/null 2>&1; then
    docker compose exec -T postgres pg_dump -U opdbot opdbot > "$DEST/db.sql"
elif [ -f "$ROOT_DIR/opdbot.db" ]; then
    # SQLite (dev)
    cp "$ROOT_DIR/opdbot.db" "$DEST/opdbot.db"
fi

# Файлы кандидатов
if [ -d "$ROOT_DIR/storage" ]; then
    tar -czf "$DEST/storage.tar.gz" -C "$ROOT_DIR" storage
fi

echo "Backup saved to $DEST"
