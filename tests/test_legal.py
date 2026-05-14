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
