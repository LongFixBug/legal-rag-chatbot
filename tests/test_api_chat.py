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


def test_chat_calculates_prize_winning_tax_without_salary_progressive_formula(client):
    client.post(
        "/api/documents/ingest",
        json={
            "title": "Luật Thuế thu nhập cá nhân 109/2025/QH15",
            "source": "tax-law-2025-prize",
            "content": (
                "Luật Thuế thu nhập cá nhân 109/2025/QH15\n\n"
                "Điều 15. Thuế thu nhập cá nhân đối với thu nhập từ trúng thưởng.\n"
                "1. Thuế thu nhập cá nhân đối với thu nhập từ trúng thưởng của cá nhân cư trú "
                "được xác định bằng thu nhập tính thuế nhân với thuế suất 10%.\n"
                "2. Thu nhập tính thuế từ trúng thưởng là phần giá trị giải thưởng vượt trên "
                "20 triệu đồng mà người nộp thuế nhận được theo từng lần trúng thưởng.\n\n"
                "Điều 29. Hiệu lực thi hành.\n"
                "Luật này có hiệu lực thi hành từ ngày 01 tháng 7 năm 2026."
            ),
        },
    )
    client.post(
        "/api/documents/ingest",
        json={
            "title": "Văn bản hợp nhất Luật Thuế thu nhập cá nhân 04/2007/QH12 và Luật sửa đổi 26/2012/QH13",
            "source": "tax-law-old-prize",
            "content": (
                "Văn bản hợp nhất Luật Thuế thu nhập cá nhân 04/2007/QH12 và Luật sửa đổi 26/2012/QH13\n\n"
                "Điều 15. Thu nhập chịu thuế từ trúng thưởng.\n"
                "Thu nhập chịu thuế từ trúng thưởng là phần giá trị giải thưởng vượt trên "
                "10 triệu đồng mà đối tượng nộp thuế nhận được theo từng lần trúng thưởng. "
                "Thuế suất đối với thu nhập từ trúng thưởng là 10%."
            ),
        },
    )

    response = client.post("/api/chat/query", json={"question": "trúng số 2 tỷ thì đóng thuế bao nhiêu"})
    assert response.status_code == 200
    answer = response.json()["answer"]

    assert "199.000.000 đồng" in answer
    assert "198.000.000 đồng" in answer
    assert "lũy tiến" in answer
    assert "thu nhập khác" in answer
    assert "Không cần" in answer


def test_chat_handles_inheritance_tax_question_without_forcing_the_reader_to_parse_laws(client):
    client.post(
        "/api/documents/ingest",
        json={
            "title": "Luật Thuế thu nhập cá nhân 109/2025/QH15",
            "source": "tax-law-2025-inheritance",
            "content": (
                "Luật Thuế thu nhập cá nhân 109/2025/QH15\n\n"
                "Điều 18. Thuế thu nhập cá nhân đối với thu nhập từ nhận thừa kế, quà tặng.\n"
                "1. Thuế thu nhập cá nhân đối với thu nhập từ nhận thừa kế, quà tặng của cá nhân cư trú "
                "được xác định bằng thu nhập tính thuế nhân với thuế suất 10%.\n"
                "2. Thu nhập tính thuế từ nhận thừa kế, quà tặng là phần giá trị tài sản thừa kế, quà tặng "
                "vượt trên 20 triệu đồng mà người nộp thuế nhận được theo từng lần nhận thừa kế, quà tặng."
            ),
        },
    )
    client.post(
        "/api/documents/ingest",
        json={
            "title": "Văn bản hợp nhất Luật Thuế thu nhập cá nhân 04/2007/QH12 và Luật sửa đổi 26/2012/QH13",
            "source": "tax-law-old-inheritance",
            "content": (
                "Văn bản hợp nhất Luật Thuế thu nhập cá nhân 04/2007/QH12 và Luật sửa đổi 26/2012/QH13\n\n"
                "Điều 18. Thu nhập chịu thuế từ thừa kế, quà tặng.\n"
                "Thu nhập chịu thuế từ nhận thừa kế, quà tặng là phần giá trị tài sản vượt trên 10 triệu đồng "
                "mà người nộp thuế nhận được theo từng lần nhận thừa kế, quà tặng. Thuế suất là 10%."
            ),
        },
    )

    response = client.post("/api/chat/query", json={"question": "được thừa kế 3 tỷ thì có đóng thuế không"})
    assert response.status_code == 200

    payload = response.json()
    answer = payload["answer"].lower()
    assert "thừa kế" in answer
    assert "tiền mặt 3 tỷ" in answer
    assert "bất động sản" in answer
    assert "299.000.000" in answer or "298.000.000" in answer
    assert all("Nghị định 65/2013/NĐ-CP" not in citation["title"] for citation in payload["citations"])


def test_chat_answers_disability_tax_question_directly(client):
    client.post(
        "/api/documents/ingest",
        json={
            "title": "Luật Thuế thu nhập cá nhân 109/2025/QH15",
            "source": "tax-law-2025-disability",
            "content": (
                "Luật Thuế thu nhập cá nhân 109/2025/QH15\n\n"
                "Điều 5. Các trường hợp miễn thuế, giảm thuế khác.\n"
                "Người nộp thuế gặp khó khăn do thiên tai, dịch bệnh, hoả hoạn, tai nạn, "
                "bệnh hiểm nghèo ảnh hưởng đến khả năng nộp thuế thì được giảm thuế tương ứng "
                "với mức độ thiệt hại nhưng không vượt quá số thuế phải nộp.\n\n"
                "Điều 10. Giảm trừ gia cảnh.\n"
                "Người phụ thuộc bao gồm con là người mất năng lực hành vi dân sự, người khuyết tật, "
                "không có khả năng lao động."
            ),
        },
    )
    client.post(
        "/api/documents/ingest",
        json={
            "title": "Thông tư 111/2013/TT-BTC hướng dẫn thuế thu nhập cá nhân",
            "source": "tax-circular-111-disability",
            "content": (
                "Thông tư 111/2013/TT-BTC hướng dẫn thuế thu nhập cá nhân\n\n"
                "Điều 4. Giảm thuế.\n"
                "Người nộp thuế gặp khó khăn do thiên tai, hỏa hoạn, tai nạn, bệnh hiểm nghèo "
                "ảnh hưởng đến khả năng nộp thuế thì được xét giảm thuế tương ứng với mức độ thiệt hại.\n\n"
                "Điều 9. Các khoản giảm trừ.\n"
                "Người khuyết tật, không có khả năng lao động là người thuộc đối tượng điều chỉnh "
                "của pháp luật về người khuyết tật."
            ),
        },
    )

    response = client.post("/api/chat/query", json={"question": "tôi bị khuyết tật thì đóng thuế như thế nào"})
    assert response.status_code == 200

    answer = response.json()["answer"]
    assert "không tự động được miễn toàn bộ thuế TNCN" in answer
    assert "tiền lương, tiền công" in answer
    assert "xét giảm thuế" in answer
    assert "người phụ thuộc" in answer
    assert "Dựa trên các văn bản đã nạp" not in answer


def test_chat_answers_worker_tax_liability_question_directly(client):
    client.post(
        "/api/documents/ingest",
        json={
            "title": "Luật Thuế thu nhập cá nhân 109/2025/QH15",
            "source": "tax-law-2025-liability",
            "content": (
                "Luật Thuế thu nhập cá nhân 109/2025/QH15\n\n"
                "Điều 2. Người nộp thuế.\n"
                "Người nộp thuế thu nhập cá nhân là cá nhân cư trú có thu nhập chịu thuế "
                "quy định tại Điều 3 của Luật này phát sinh trong và ngoài lãnh thổ Việt Nam "
                "và cá nhân không cư trú có thu nhập chịu thuế phát sinh trong lãnh thổ Việt Nam.\n\n"
                "Điều 3. Thu nhập chịu thuế.\n"
                "Thu nhập chịu thuế thu nhập cá nhân gồm các loại thu nhập sau đây, trừ thu nhập "
                "được miễn thuế: thu nhập từ kinh doanh; thu nhập từ tiền lương, tiền công.\n\n"
                "Điều 8. Thuế thu nhập cá nhân đối với thu nhập từ tiền lương, tiền công.\n"
                "Thu nhập tính thuế đối với thu nhập từ tiền lương, tiền công là tổng thu nhập chịu thuế "
                "trừ đi các khoản đóng góp bảo hiểm bắt buộc và các khoản giảm trừ.\n\n"
                "Điều 10. Giảm trừ gia cảnh.\n"
                "Mức giảm trừ đối với người nộp thuế là 15,5 triệu đồng/tháng và mỗi người phụ thuộc "
                "là 6,2 triệu đồng/tháng.\n\n"
                "Điều 21. Thuế thu nhập cá nhân đối với thu nhập từ tiền lương, tiền công.\n"
                "Thuế thu nhập cá nhân đối với thu nhập từ tiền lương, tiền công của cá nhân không cư trú "
                "được xác định bằng tổng số tiền lương, tiền công do thực hiện công việc tại Việt Nam nhân với thuế suất 20%."
            ),
        },
    )

    response = client.post(
        "/api/chat/query",
        json={"question": "người trong độ tuổi lao động phải đáp ứng điều kiện nào thì sẽ đóng thuế tncn"},
    )
    assert response.status_code == 200

    answer = response.json()["answer"]
    assert "độ tuổi lao động không phải là điều kiện quyết định" in answer
    assert "thu nhập chịu thuế" in answer
    assert "15,5 triệu đồng/tháng" in answer
    assert "20%" in answer
    assert "Dựa trên các văn bản đã nạp" not in answer


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
