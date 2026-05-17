from app.services.legal import LegalTextService


def test_guess_title_supports_military_regulation_document_types():
    service = LegalTextService()

    assert (
        service.guess_title(
            "Văn bản hợp nhất 80/VBHN-VPQH năm 2025 hợp nhất Luật Nghĩa vụ quân sự\n\nĐiều 1. Phạm vi điều chỉnh.",
            "fallback",
        )
        == "Văn bản hợp nhất 80/VBHN-VPQH năm 2025 hợp nhất Luật Nghĩa vụ quân sự"
    )
    assert (
        service.guess_title(
            "Thông tư 105/2023/TT-BQP về khám sức khỏe nghĩa vụ quân sự\n\nĐiều 1. Phạm vi điều chỉnh.",
            "fallback",
        )
        == "Thông tư 105/2023/TT-BQP về khám sức khỏe nghĩa vụ quân sự"
    )
    assert (
        service.guess_title(
            "Nghị định 120/2013/NĐ-CP xử phạt vi phạm hành chính trong lĩnh vực quốc phòng\n\nĐiều 1. Phạm vi điều chỉnh.",
            "fallback",
        )
        == "Nghị định 120/2013/NĐ-CP xử phạt vi phạm hành chính trong lĩnh vực quốc phòng"
    )


def test_has_phrase_overlap_detects_multiword_legal_topics():
    service = LegalTextService()

    assert service.has_phrase_overlap(
        "đang học đại học có được tạm hoãn nghĩa vụ quân sự không",
        "Điều 41 quy định tạm hoãn gọi nhập ngũ khi đang học đại học hệ chính quy",
    )


def test_legal_search_article_filter(client):
    client.post("/api/documents/preload")
    response = client.get("/api/legal/search", params={"q": "độ tuổi gọi nhập ngũ", "article": "Điều 30"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]
    assert all(item["article"] == "Điều 30" for item in payload["results"])


def test_legal_search_handles_unaccented_article_reference(client):
    client.post("/api/documents/preload")
    response = client.get("/api/legal/search", params={"q": "Dieu30", "top_k": 3})
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]
    assert payload["results"][0]["article"] == "Điều 30"


def test_legal_search_falls_back_to_exact_article_match_when_vector_search_misses(client):
    client.post("/api/documents/preload")

    async def empty_search(*args, **kwargs):
        return []

    client.app.state.services.vector_store.search = empty_search

    response = client.get("/api/legal/search", params={"q": "Dieu30", "top_k": 3})
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]
    assert payload["results"][0]["article"] == "Điều 30"


def test_legal_search_promotes_topical_title_matches_for_short_resolutions(client):
    client.post(
        "/api/documents/ingest",
        json={
            "title": "Văn bản hợp nhất 88/VBHN-BQP về khám sức khỏe nghĩa vụ quân sự",
            "source": "military-health",
            "content": (
                "Văn bản hợp nhất 88/VBHN-BQP về khám sức khỏe nghĩa vụ quân sự\n\n"
                "Điều 4. Tiêu chuẩn sức khỏe thực hiện nghĩa vụ quân sự.\n"
                "Tiêu chuẩn chung là đạt sức khỏe loại 1, loại 2 hoặc loại 3."
            ),
        },
    )
    client.post(
        "/api/documents/ingest",
        json={
            "title": "Văn bản hợp nhất 04/VBHN-BQP về xử phạt nghĩa vụ quân sự",
            "source": "military-penalty",
            "content": (
                "Văn bản hợp nhất 04/VBHN-BQP về xử phạt nghĩa vụ quân sự\n\n"
                "Điều 6. Vi phạm quy định về kiểm tra, khám sức khỏe thực hiện nghĩa vụ quân sự."
            ),
        },
    )

    response = client.get(
        "/api/legal/search",
        params={
            "q": "tieu chuan suc khoe thuc hien nghia vu quan su",
            "top_k": 3,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]
    assert payload["results"][0]["title"] == "Văn bản hợp nhất 88/VBHN-BQP về khám sức khỏe nghĩa vụ quân sự"
