#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required, for example postgresql+asyncpg://raguser:ragpass@localhost:5433/ragdb" >&2
  exit 2
fi

uv run alembic upgrade head
