# Operations Runbook

## Quick Checks

1. Start stack: `docker compose --profile llama up -d --build`
2. Check containers: `make ps`
3. Check liveness: `curl -sS http://127.0.0.1:8000/health`
4. Check readiness: `curl -sS http://127.0.0.1:8000/health/ready`
5. Check metrics: `curl -sS http://127.0.0.1:8000/health/metrics`
6. Run smoke test: `bash scripts/smoke_test.sh`

## Database Migrations

- Run migrations: `DATABASE_URL="postgresql+asyncpg://raguser:ragpass@localhost:5433/ragdb" make migrate`
- Existing databases created before Alembic can be baselined with `uv run alembic stamp head` after confirming schema matches `alembic/versions/0001_initial_schema.py`.
- New PostgreSQL environments should run `make migrate` before API startup or before the first ingest.
- The app still keeps local fallback storage for development, but production PostgreSQL schema changes should go through Alembic revisions.

## Backup And Restore

- Create a backup: `BACKUP_DIR=backups/manual-$(date -u +%Y%m%dT%H%M%SZ) scripts/backup_data.sh`
- Restore a backup: `scripts/restore_data.sh backups/<backup-dir>`
- Backup includes PostgreSQL metadata/chat history and Qdrant vector storage.
- Restore should be followed by restarting Qdrant/API and running `bash scripts/smoke_test.sh`.
- If embedding model or `EMBEDDING_DIMENSION` changed since the backup, prefer reindexing instead of restoring an old Qdrant snapshot.

## Retention Cleanup

- Configure `UPLOADED_DOCUMENT_RETENTION_DAYS` and `CHAT_HISTORY_RETENTION_DAYS`.
- `0` disables the corresponding retention rule.
- Trigger cleanup: `curl -X POST http://127.0.0.1:8000/api/maintenance/retention/purge -H "X-Admin-Token: $ADMIN_TOKEN"`
- Cleanup only deletes uploaded documents for document retention; curated preload files are preserved.

## Chat Returns Weak Or No Answer

- Check `/health/ready` for degraded `llm`, `embedding`, `metadata_store`, or `vector_store`.
- Reindex curated corpus: `curl -X POST http://127.0.0.1:8000/api/documents/reindex -H "X-Admin-Token: $ADMIN_TOKEN"`
- Confirm Qdrant collection matches embedding dimension: `QDRANT_COLLECTION` and `EMBEDDING_DIMENSION`.
- Run evals: `make eval`.

## Qdrant Empty Or Retrieval Looks Wrong

- Run `make ready` and verify `vector_store.ready` is true.
- Reindex data with `/api/documents/reindex`.
- If embedding model or dimension changed, use a new Qdrant collection name before reindexing.
- Avoid indexing noisy OCR extracts directly; curate text into `data/nghia-vu-quan-su-curated-*.txt`.

## PostgreSQL Down

- Check container status: `docker compose ps postgres`.
- Check logs: `docker compose logs postgres`.
- Verify `DATABASE_URL` uses `postgresql+asyncpg://`.
- In local fallback mode, clear `.storage` only if you intentionally want to reset local metadata.

## llama.cpp Timeout Or Model Unavailable

- Check exposed models:
  - Chat: `curl -sS http://127.0.0.1:8080/v1/models`
  - Embedding: `curl -sS http://127.0.0.1:8081/v1/models`
- Ensure `LLM_MODEL` and `EMBEDDING_MODEL` exactly match model ids.
- Increase `LLM_TIMEOUT_SECONDS` or `EMBEDDING_TIMEOUT_SECONDS` if the machine is slow.
- The app can run degraded with fallback answer/embedding, but answer quality will be lower.

## Upload Or Ingest Fails

- If status is `401`, set `ADMIN_TOKEN` and pass `X-Admin-Token`.
- If status is `413`, lower file size or raise `MAX_UPLOAD_BYTES`.
- If status is `415`, check `ALLOWED_UPLOAD_EXTENSIONS` and `ALLOWED_UPLOAD_MIME_TYPES`.
- If status is `429`, wait for the rate-limit window or raise the relevant rate-limit env value.

## Rollback

- Use Git to return to the last known good commit.
- Rebuild Docker after rollback: `docker compose --profile llama up -d --build`.
- Re-run `bash scripts/smoke_test.sh` and `make eval`.
