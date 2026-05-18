from app.db.models import ConversationRecord, DocumentRecord


async def _seed_expired_records(client):
    services = client.app.state.services
    old_timestamp = "2020-01-01T00:00:00+00:00"
    fresh_timestamp = "2999-01-01T00:00:00+00:00"

    await services.metadata_store.upsert_document(
        DocumentRecord(
            id="old-upload",
            title="Old upload",
            source="old.txt",
            doc_type="uploaded_file",
            summary="old",
            created_at=old_timestamp,
        )
    )
    await services.metadata_store.upsert_document(
        DocumentRecord(
            id="fresh-upload",
            title="Fresh upload",
            source="fresh.txt",
            doc_type="uploaded_file",
            summary="fresh",
            created_at=fresh_timestamp,
        )
    )
    await services.metadata_store.upsert_document(
        DocumentRecord(
            id="curated-source",
            title="Curated source",
            source="data/curated.txt",
            doc_type="txt",
            summary="curated",
            created_at=old_timestamp,
        )
    )
    await services.metadata_store.create_conversation(
        ConversationRecord(id="old-conversation", title="Old", created_at=old_timestamp, updated_at=old_timestamp)
    )
    await services.metadata_store.create_conversation(
        ConversationRecord(id="fresh-conversation", title="Fresh", created_at=fresh_timestamp, updated_at=fresh_timestamp)
    )


def test_retention_purge_removes_expired_uploaded_documents_and_conversations(client):
    client.app.state.services.settings.uploaded_document_retention_days = 30
    client.app.state.services.settings.chat_history_retention_days = 30
    client.portal.call(_seed_expired_records, client)

    response = client.post("/api/maintenance/retention/purge")
    assert response.status_code == 200
    assert response.json() == {"documents_deleted": 1, "conversations_deleted": 1}

    documents = client.get("/api/documents")
    assert documents.status_code == 200
    document_ids = {item["id"] for item in documents.json()}
    assert "old-upload" not in document_ids
    assert "fresh-upload" in document_ids
    assert "curated-source" in document_ids

    old_history = client.get("/api/chat/conversations/old-conversation")
    assert old_history.status_code == 404
    fresh_history = client.get("/api/chat/conversations/fresh-conversation")
    assert fresh_history.status_code == 200


def test_retention_purge_requires_admin_token_when_configured(client):
    client.app.state.services.settings.admin_token = "secret-token"

    denied = client.post("/api/maintenance/retention/purge")
    assert denied.status_code == 401

    allowed = client.post("/api/maintenance/retention/purge", headers={"X-Admin-Token": "secret-token"})
    assert allowed.status_code == 200
