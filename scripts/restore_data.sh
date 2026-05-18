#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <backup-dir>" >&2
  exit 2
fi

BACKUP_DIR="$1"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-rag-postgres}"
QDRANT_CONTAINER="${QDRANT_CONTAINER:-rag-qdrant}"
POSTGRES_USER="${POSTGRES_USER:-raguser}"
POSTGRES_DB="${POSTGRES_DB:-ragdb}"

if [[ ! -f "$BACKUP_DIR/postgres.sql" ]]; then
  echo "Missing $BACKUP_DIR/postgres.sql" >&2
  exit 1
fi

if [[ ! -f "$BACKUP_DIR/qdrant-storage.tar.gz" ]]; then
  echo "Missing $BACKUP_DIR/qdrant-storage.tar.gz" >&2
  exit 1
fi

echo "Restoring PostgreSQL from $BACKUP_DIR/postgres.sql"
docker exec -i "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" "$POSTGRES_DB" < "$BACKUP_DIR/postgres.sql"

echo "Restoring Qdrant storage from $BACKUP_DIR/qdrant-storage.tar.gz"
docker run --rm --volumes-from "$QDRANT_CONTAINER" -v "$PWD/$BACKUP_DIR:/backup" alpine sh -c \
  "rm -rf /qdrant/storage/* && tar -xzf /backup/qdrant-storage.tar.gz -C /qdrant/storage"

echo "Restore complete. Restart qdrant/api if they are already running."
