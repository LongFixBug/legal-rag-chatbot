from app.services.legal import LegalTextService


def test_guess_title_supports_tax_regulation_document_types():
    service = LegalTextService()

    assert (
        service.guess_title(
            "Nghị định 65/2013/NĐ-CP hướng dẫn Luật Thuế thu nhập cá nhân\n\nĐiều 1. Phạm vi điều chỉnh.",
            "fallback",
        )
        == "Nghị định 65/2013/NĐ-CP hướng dẫn Luật Thuế thu nhập cá nhân"
    )
    assert (
        service.guess_title(
            "Thông tư 111/2013/TT-BTC hướng dẫn thuế thu nhập cá nhân\n\nĐiều 1. Phạm vi điều chỉnh.",
            "fallback",
        )
        == "Thông tư 111/2013/TT-BTC hướng dẫn thuế thu nhập cá nhân"
    )
    assert (
        service.guess_title(
            "Văn bản hợp nhất Luật Thuế thu nhập cá nhân 04/2007/QH12 và Luật sửa đổi 26/2012/QH13\n\nĐiều 1. Phạm vi điều chỉnh.",
            "fallback",
        )
        == "Văn bản hợp nhất Luật Thuế thu nhập cá nhân 04/2007/QH12 và Luật sửa đổi 26/2012/QH13"
    )


def test_has_phrase_overlap_detects_multiword_legal_topics():
    service = LegalTextService()

    assert service.has_phrase_overlap(
        "Mức giảm trừ gia cảnh đối với thuế thu nhập cá nhân của người lao động từ năm 2026 là bao nhiêu?",
        "Nghị quyết 110/2025/UBTVQH15 điều chỉnh mức giảm trừ gia cảnh của thuế thu nhập cá nhân",
    )


def test_legal_search_article_filter(client):
    client.post("/api/documents/preload")
    response = client.get("/api/legal/search", params={"q": "quyền thành lập doanh nghiệp", "article": "Điều 17"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]
    assert all(item["article"] == "Điều 17" for item in payload["results"])


def test_legal_search_handles_unaccented_article_reference(client):
    client.post("/api/documents/preload")
    response = client.get("/api/legal/search", params={"q": "Dieu17", "top_k": 3})
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]
    assert payload["results"][0]["article"] == "Điều 17"


def test_legal_search_falls_back_to_exact_article_match_when_vector_search_misses(client):
    client.post("/api/documents/preload")

    async def empty_search(*args, **kwargs):
        return []

    client.app.state.services.vector_store.search = empty_search

    response = client.get("/api/legal/search", params={"q": "Dieu17", "top_k": 3})
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]
    assert payload["results"][0]["article"] == "Điều 17"


def test_legal_search_promotes_topical_title_matches_for_short_resolutions(client):
    client.post(
        "/api/documents/ingest",
        json={
            "title": "Nghị quyết 110/2025/UBTVQH15 điều chỉnh mức giảm trừ gia cảnh",
            "source": "tax-resolution",
            "content": (
                "Nghị quyết 110/2025/UBTVQH15 điều chỉnh mức giảm trừ gia cảnh\n\n"
                "Mức giảm trừ đối với đối tượng nộp thuế là 15,5 triệu đồng/tháng "
                "(186 triệu đồng/năm).\n"
                "Mức giảm trừ đối với mỗi người phụ thuộc là 6,2 triệu đồng/tháng.\n"
                "Nghị quyết này có hiệu lực từ ngày 01 tháng 01 năm 2026 và áp dụng "
                "từ kỳ tính thuế năm 2026."
            ),
        },
    )
    client.post(
        "/api/documents/ingest",
        json={
            "title": "Luật Thuế thu nhập cá nhân 109/2025/QH15",
            "source": "tax-law",
            "content": (
                "Luật Thuế thu nhập cá nhân 109/2025/QH15\n\n"
                "Điều 3. Thu nhập chịu thuế.\n"
                "Thu nhập từ tiền lương, tiền công thuộc diện chịu thuế theo quy định của luật này."
            ),
        },
    )

    response = client.get(
        "/api/legal/search",
        params={
            "q": "Muc giam tru gia canh doi voi thue thu nhap ca nhan cua nguoi lao dong tu nam 2026 la bao nhieu",
            "top_k": 3,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]
    assert payload["results"][0]["title"] == "Nghị quyết 110/2025/UBTVQH15 điều chỉnh mức giảm trừ gia cảnh"
