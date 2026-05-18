#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-backups/$(date -u +%Y%m%dT%H%M%SZ)}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-rag-postgres}"
QDRANT_CONTAINER="${QDRANT_CONTAINER:-rag-qdrant}"
POSTGRES_USER="${POSTGRES_USER:-raguser}"
POSTGRES_DB="${POSTGRES_DB:-ragdb}"

mkdir -p "$BACKUP_DIR"

echo "Backing up PostgreSQL to $BACKUP_DIR/postgres.sql"
docker exec "$POSTGRES_CONTAINER" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$BACKUP_DIR/postgres.sql"

echo "Backing up Qdrant storage to $BACKUP_DIR/qdrant-storage.tar.gz"
docker run --rm --volumes-from "$QDRANT_CONTAINER" -v "$PWD/$BACKUP_DIR:/backup" alpine \
  tar -czf /backup/qdrant-storage.tar.gz -C /qdrant/storage .

echo "Backup complete: $BACKUP_DIR"
