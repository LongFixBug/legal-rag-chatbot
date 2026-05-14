def test_chat_returns_citations(client):
    preload = client.post("/api/documents/preload")
    assert preload.status_code == 200

    response = client.post("/api/chat/query", json={"question": "Điều 17 quy định gì về quyền thành lập doanh nghiệp?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation_id"]
    assert payload["retrieved_chunks"] >= 1
    assert payload["citations"]
    assert payload["history_used"] == 0
    assert "Điều 17" in payload["answer"] or "căn cứ" in payload["answer"].lower()


def test_chat_uses_history_with_same_conversation(client):
    client.post("/api/documents/preload")
    first = client.post("/api/chat/query", json={"question": "Điều 17 nói về vấn đề gì?"})
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    follow_up = client.post(
        "/api/chat/query",
        json={"question": "Điều đó áp dụng cho ai?", "conversation_id": conversation_id},
    )
    assert follow_up.status_code == 200
    payload = follow_up.json()
    assert payload["conversation_id"] == conversation_id
    assert payload["history_used"] >= 2


def test_conversations_are_isolated(client):
    client.post("/api/documents/preload")
    first = client.post("/api/chat/query", json={"question": "Điều 17 quy định gì?"})
    assert first.status_code == 200

    second = client.post("/api/chat/query", json={"question": "Tiền lương là gì?"})
    assert second.status_code == 200
    assert second.json()["history_used"] == 0
    assert second.json()["conversation_id"] != first.json()["conversation_id"]


def test_conversation_history_and_delete(client):
    client.post("/api/documents/preload")
    first = client.post("/api/chat/query", json={"question": "Điều 17 quy định gì?"})
    conversation_id = first.json()["conversation_id"]

    history = client.get(f"/api/chat/conversations/{conversation_id}")
    assert history.status_code == 200
    items = history.json()
    assert len(items) == 2
    assert items[0]["role"] == "user"
    assert items[1]["role"] == "assistant"

    conversations = client.get("/api/chat/conversations")
    assert conversations.status_code == 200
    assert any(item["id"] == conversation_id for item in conversations.json())

    deleted = client.delete(f"/api/chat/conversations/{conversation_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    history_after_delete = client.get(f"/api/chat/conversations/{conversation_id}")
    assert history_after_delete.status_code == 404
