def test_ingest_list_delete_document(client):
    ingest = client.post(
        "/api/documents/ingest",
        json={
            "title": "Luật mẫu",
            "source": "manual-test",
            "content": "Luật Mẫu\n\nĐiều 1. Phạm vi điều chỉnh.\n1. Văn bản này dùng để test ingest.",
        },
    )
    assert ingest.status_code == 200
    payload = ingest.json()
    document_id = payload["document"]["id"]
    assert payload["chunks_indexed"] >= 1

    listed = client.get("/api/documents")
    assert listed.status_code == 200
    assert any(item["id"] == document_id for item in listed.json())

    deleted = client.delete(f"/api/documents/{document_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_upload_html_document(client):
    html = """
    <html><body>
      <h1>Luật Thử Nghiệm</h1>
      <p>Điều 22. Nghĩa vụ công bố thông tin.</p>
      <p>1. Doanh nghiệp phải công bố thông tin trung thực.</p>
    </body></html>
    """.strip()
    response = client.post(
        "/api/documents/upload",
        data={"title": "Luật Thử Nghiệm"},
        files={"file": ("legal.html", html.encode("utf-8"), "text/html")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["doc_type"] == "uploaded_file"
    assert payload["chunks_indexed"] >= 1
