#!/bin/bash
# NovelCraft encrypted backup + Telegram alert
# Usage: AGE_PUBKEY=age1... TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... ./scripts/backup.sh
set -euo pipefail

DB_URL="${DATABASE_URL:-postgresql://genius@localhost/novelcraft_dev}"
# Ensure pg_dump uses TCP (not Unix socket) for password-less auth
export PGHOST=localhost PGUSER=genius PGDATABASE=novelcraft_dev
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
AGE_PUBKEY="${AGE_PUBKEY:-}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
RAW="$BACKUP_DIR/novelcraft_${TIMESTAMP}.sql"
ENC="$BACKUP_DIR/novelcraft_${TIMESTAMP}.sql.age"

send_alert() {
    local msg="$1"
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" -d "text=${msg}" > /dev/null || true
    fi
}

echo "[$(date)] Starting backup → $ENC"
send_alert "🔄 NovelCraft backup starting..."

DB_USER=$(echo "$DB_URL" | sed -n 's|.*://\([^:]*\).*|\1|p')
DB_PASS=$(echo "$DB_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DB_URL" | sed -n 's|.*@\([^/]*\)/.*|\1|p')
DB_NAME=$(echo "$DB_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

if [ -n "$DB_PASS" ]; then
    PGPASSWORD="$DB_PASS" pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl > "$RAW" 2>/tmp/nc_backup_err
else
    pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl > "$RAW" 2>/tmp/nc_backup_err
fi

if [ -n "$AGE_PUBKEY" ]; then
    age -r "$AGE_PUBKEY" -o "$ENC" "$RAW" && rm "$RAW"
    echo "[$(date)] Encrypted → $ENC"
else
    mv "$RAW" "$ENC"
    echo "[$(date)] Saved (unencrypted — set AGE_PUBKEY to encrypt)"
fi

find "$BACKUP_DIR" -name "novelcraft_*" -mtime "+${RETENTION_DAYS}" -delete

if command -v rclone &>/dev/null && [ -n "${RCLONE_REMOTE:-}" ]; then
    rclone copy "$BACKUP_DIR" "$RCLONE_REMOTE" --include "novelcraft_*"
fi

SIZE=$(du -h "$ENC" | cut -f1)
echo "[$(date)] Backup complete ($SIZE)"
send_alert "✅ NovelCraft backup done — $SIZE"
