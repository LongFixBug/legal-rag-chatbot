from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MILITARY_FILES = [
    "nghia-vu-quan-su-2015.txt",
    "nghia-vu-quan-su-kham-suc-khoe-105-2023.txt",
    "nghia-vu-quan-su-xu-phat-120-2013-37-2022.txt",
]


def seed_military_documents(client) -> None:
    for filename in MILITARY_FILES:
        path = PROJECT_ROOT / "data" / filename
        response = client.post(
            "/api/documents/ingest",
            json={
                "title": path.stem.replace("-", " ").title(),
                "source": f"test/{filename}",
                "content": path.read_text(encoding="utf-8"),
            },
        )
        assert response.status_code == 200


def test_military_age_question_answers_directly(client):
    seed_military_documents(client)

    response = client.post("/api/chat/query", json={"question": "bao nhiêu tuổi thì phải đi nghĩa vụ quân sự"})

    assert response.status_code == 200
    payload = response.json()
    answer = payload["answer"]
    assert "đủ 18 tuổi" in answer
    assert "hết 25 tuổi" in answer
    assert "hết 27 tuổi" in answer
    assert "Điều 30" in answer
    assert any(citation["article"] == "Điều 30" for citation in payload["citations"])


def test_military_student_deferment_question_answers_directly(client):
    seed_military_documents(client)

    response = client.post("/api/chat/query", json={"question": "đang học đại học có được tạm hoãn nghĩa vụ quân sự không"})

    assert response.status_code == 200
    answer = response.json()["answer"]
    assert "tạm hoãn" in answer
    assert "một khóa đào tạo" in answer
    assert "hết 27 tuổi" in answer
    assert "Điều 41" in answer


def test_military_myopia_question_answers_with_health_caveat(client):
    seed_military_documents(client)

    response = client.post("/api/chat/query", json={"question": "cận thị 4 độ có phải đi nghĩa vụ quân sự không"})

    assert response.status_code == 200
    answer = response.json()["answer"]
    assert "không nên kết luận chỉ dựa vào số độ cận" in answer
    assert "từ -4D đến dưới -5D" in answer
    assert "điểm 5" in answer
    assert "Hội đồng khám sức khỏe" in answer


def test_military_exam_penalty_question_answers_directly(client):
    seed_military_documents(client)

    response = client.post("/api/chat/query", json={"question": "không đi khám sức khỏe nghĩa vụ quân sự bị phạt bao nhiêu"})

    assert response.status_code == 200
    answer = response.json()["answer"]
    assert "10 đến 12 triệu đồng" in answer
    assert "25 đến 35 triệu đồng" in answer
    assert "Điều 6" in answer
