def test_chat_without_documents(client):
    response = client.post("/api/chat/query", json={"question": "Hợp đồng lao động là gì?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation_id"]
    assert payload["retrieved_chunks"] == 0
    assert "Chưa có căn cứ" in payload["answer"]
