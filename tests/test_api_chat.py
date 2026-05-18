def test_chat_returns_military_answer_with_citations(client):
    preload = client.post("/api/documents/preload")
    assert preload.status_code == 200

    response = client.post("/api/chat/query", json={"question": "bao nhiêu tuổi thì phải đi nghĩa vụ quân sự?"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["conversation_id"]
    assert payload["retrieved_chunks"] >= 1
    assert payload["citations"]
    assert payload["history_used"] == 0
    assert payload["abstained"] is False
    assert payload["confidence"] > 0.0
    assert "đủ 18 tuổi" in payload["answer"]
    assert "Điều 30" in payload["answer"]


def test_chat_refuses_out_of_scope_question(client):
    client.post("/api/documents/preload")

    response = client.post("/api/chat/query", json={"question": "trúng số 2 tỷ thì đóng thuế bao nhiêu"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["retrieved_chunks"] == 0
    assert payload["citations"] == []
    assert "chỉ hỗ trợ" in payload["answer"]
    assert "nghĩa vụ quân sự" in payload["answer"]
    assert payload["abstained"] is True
    assert payload["confidence"] == 0.0


def test_chat_abstains_when_no_military_evidence_is_indexed(client):
    response = client.post("/api/chat/query", json={"question": "cận thị 4 độ có đi nghĩa vụ quân sự không?"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["abstained"] is True
    assert payload["retrieved_chunks"] == 0
    assert payload["citations"] == []
    assert "Chưa tìm thấy căn cứ đủ mạnh" in payload["answer"]
    assert payload["confidence"] == 0.0


def test_chat_abstains_when_retrieved_context_is_not_relevant_enough(client):
    client.post(
        "/api/documents/ingest",
        json={
            "title": "Văn bản hợp nhất 04/VBHN-BQP về xử phạt nghĩa vụ quân sự",
            "source": "penalty-only",
            "content": (
                "Văn bản hợp nhất 04/VBHN-BQP về xử phạt nghĩa vụ quân sự\n\n"
                "Điều 6. Vi phạm quy định về kiểm tra, khám sức khỏe thực hiện nghĩa vụ quân sự.\n"
                "Không chấp hành lệnh gọi kiểm tra, khám sức khỏe có thể bị xử phạt."
            ),
        },
    )

    response = client.post("/api/chat/query", json={"question": "con gái có phải đi nghĩa vụ quân sự không?"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["abstained"] is True
    assert payload["citations"] == []
    assert "Chưa tìm thấy căn cứ đủ mạnh" in payload["answer"]


def test_chat_uses_history_with_same_conversation(client):
    client.post("/api/documents/preload")
    first = client.post("/api/chat/query", json={"question": "bao nhiêu tuổi thì đi nghĩa vụ quân sự?"})
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    follow_up = client.post(
        "/api/chat/query",
        json={"question": "nếu đang học đại học thì sao?", "conversation_id": conversation_id},
    )
    assert follow_up.status_code == 200
    payload = follow_up.json()
    assert payload["conversation_id"] == conversation_id
    assert payload["history_used"] >= 2


def test_conversations_are_isolated(client):
    client.post("/api/documents/preload")
    first = client.post("/api/chat/query", json={"question": "bao nhiêu tuổi thì đi nghĩa vụ quân sự?"})
    assert first.status_code == 200

    second = client.post("/api/chat/query", json={"question": "cận thị 4 độ có đi nghĩa vụ quân sự không?"})
    assert second.status_code == 200
    assert second.json()["history_used"] == 0
    assert second.json()["conversation_id"] != first.json()["conversation_id"]


def test_conversation_history_and_delete(client):
    client.post("/api/documents/preload")
    first = client.post("/api/chat/query", json={"question": "bao nhiêu tuổi thì đi nghĩa vụ quân sự?"})
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
