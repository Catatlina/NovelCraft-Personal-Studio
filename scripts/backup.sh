#!/bin/bash
# NovelCraft backup — pg_dump | age encrypt → local + rclone remote
# Run: ./scripts/backup.sh
set -euo pipefail

DB_URL="${DATABASE_URL:-postgresql://novelcraft:novelcraft@localhost/novelcraft_dev}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
AGE_PUBKEY="${AGE_PUBKEY:-}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
RAW="$BACKUP_DIR/novelcraft_${TIMESTAMP}.sql"
ENC="$BACKUP_DIR/novelcraft_${TIMESTAMP}.sql.age"

echo "[$(date)] Starting backup → $ENC"

# Extract connection parts from DATABASE_URL
# format: postgresql://user:pass@host/db
DB_USER=$(echo "$DB_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_PASS=$(echo "$DB_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DB_URL" | sed -n 's|.*@\([^/]*\)/.*|\1|p')
DB_NAME=$(echo "$DB_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

PGPASSWORD="$DB_PASS" pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl > "$RAW"

if [ -n "$AGE_PUBKEY" ]; then
    age -r "$AGE_PUBKEY" -o "$ENC" "$RAW"
    rm "$RAW"
    echo "[$(date)] Encrypted → $ENC"
else
    mv "$RAW" "$ENC"
    echo "[$(date)] Saved (unencrypted) → $ENC"
fi

# Cleanup old backups
find "$BACKUP_DIR" -name "novelcraft_*" -mtime "+${RETENTION_DAYS}" -delete

# Optional rclone sync
if command -v rclone &>/dev/null && [ -n "${RCLONE_REMOTE:-}" ]; then
    rclone copy "$BACKUP_DIR" "$RCLONE_REMOTE" --include "novelcraft_*"
    echo "[$(date)] Synced to remote: $RCLONE_REMOTE"
fi

echo "[$(date)] Backup complete ($(du -h "$ENC" | cut -f1))"
