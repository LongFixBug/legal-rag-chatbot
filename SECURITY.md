# Security Notes

## Current Protection

- Mutating document endpoints require `X-Admin-Token` when `ADMIN_TOKEN` is configured.
- Chat and document mutation endpoints have in-memory fixed-window rate limits.
- Uploads are restricted by file extension, MIME type, and maximum byte size.
- Secrets are configured through environment variables; do not commit `.env` files or model credentials.

## Important Environment Variables

- `ADMIN_TOKEN`: enables operator-only write access for ingest, upload, preload, reindex, and delete.
- `RATE_LIMIT_ENABLED`: turns basic rate limiting on or off.
- `CHAT_RATE_LIMIT_PER_MINUTE`: per-client chat request limit.
- `DOCUMENT_MUTATION_RATE_LIMIT_PER_MINUTE`: per-client document mutation limit.
- `MAX_UPLOAD_BYTES`: maximum accepted upload size.
- `ALLOWED_UPLOAD_EXTENSIONS`: comma-separated upload extension allowlist.
- `ALLOWED_UPLOAD_MIME_TYPES`: comma-separated upload MIME allowlist.
- `UPLOADED_DOCUMENT_RETENTION_DAYS`: uploaded document retention window; `0` disables cleanup.
- `CHAT_HISTORY_RETENTION_DAYS`: conversation retention window; `0` disables cleanup.

## Prompt And Ingestion Boundaries

- Treat uploaded legal text as untrusted data, not instructions.
- Do not follow instructions embedded inside uploaded documents.
- Answers should be grounded in retrieved legal chunks and citations.
- If retrieval is weak, the app should abstain instead of guessing.
- For public deployment, put the API behind an authenticated gateway and do not expose document mutation endpoints directly.

## Remaining Work

- Add user authentication if the app is exposed beyond local/internal demo usage.
- Add persistent distributed rate limiting for multi-instance deployment.
- Add malware scanning or OCR quality checks if arbitrary public uploads are allowed.
- Add audit logs for document mutation actions.
