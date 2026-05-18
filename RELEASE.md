# Release And Rollback

## Pre-Release Checklist

1. Run tests: `uv run pytest -q`
2. Run quality evals: `make eval`
3. Compile check: `python3 -m compileall app streamlit_app tests`
4. Build image: `docker build -t legal-rag-chatbot:<version> .`
5. Run migrations against staging: `DATABASE_URL="<staging-url>" make migrate`
6. Start staging stack and run: `bash scripts/smoke_test.sh`
7. Check readiness and metrics:
   - `curl -sS <api-url>/health/ready`
   - `curl -sS <api-url>/health/metrics`

## Image Tagging

- Use immutable tags for releases, for example `legal-rag-chatbot:0.2.1`.
- Keep `latest` or `main` only as a moving convenience tag, not as a rollback target.
- Record the app image tag, Git commit, Qdrant collection, embedding model, and migration revision in release notes.

## Deployment Order

1. Backup data: `scripts/backup_data.sh`
2. Apply database migrations: `make migrate`
3. Deploy API image.
4. Deploy Streamlit image.
5. Run smoke test.
6. Monitor `/health/ready`, `/health/metrics`, and API logs.

## Rollback

1. Stop new traffic if possible.
2. Roll back API/Streamlit images to the previous immutable tag.
3. If a data migration or reindex caused the issue, restore the matching backup with `scripts/restore_data.sh`.
4. Restart API/Qdrant after restore.
5. Run smoke test and targeted evals.

## Staging Expectation

- Staging should use PostgreSQL and Qdrant, not local JSON/vector fallback.
- Staging may use smaller models, but model ids and embedding dimension must be explicit.
- Any parser, chunking, embedding, or Qdrant collection change should be tested in staging before demo/production.
