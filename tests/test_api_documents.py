from pathlib import Path


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
      <p>Điều 22. Nghĩa vụ thử nghiệm.</p>
      <p>1. Công dân phải cung cấp thông tin trung thực.</p>
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


def test_preload_skips_readme_files(client):
    data_dir = Path(client.app.state.services.settings.data_dir)
    (data_dir / "README.md").write_text("Hướng dẫn nội bộ, không phải văn bản pháp luật.", encoding="utf-8")
    (data_dir / "military-law.txt").write_text(
        "Văn bản hợp nhất 80/VBHN-VPQH năm 2025 hợp nhất Luật Nghĩa vụ quân sự\n\nĐiều 6. Nghĩa vụ phục vụ tại ngũ.",
        encoding="utf-8",
    )

    response = client.post("/api/documents/preload")
    assert response.status_code == 200
    assert response.json()["documents_ingested"] == 2

    listed = client.get("/api/documents")
    assert listed.status_code == 200
    sources = {item["source"] for item in listed.json()}
    assert "military-law.txt" not in sources
    assert str(data_dir / "README.md") not in sources
    assert str(data_dir / "military-law.txt") in sources


def test_reindex_replaces_preloaded_documents(client):
    data_dir = Path(client.app.state.services.settings.data_dir)
    client.app.state.services.settings.preload_include_pattern = "sample.txt"
    target = data_dir / "sample.txt"
    stale = data_dir / "old-ocr.txt"

    preload = client.post("/api/documents/preload")
    assert preload.status_code == 200
    assert preload.json()["documents_ingested"] == 1

    stale.write_text("Văn bản OCR lỗi\n\nĐiều 99. Header footer rác.", encoding="utf-8")
    stale_ingest = client.post(
        "/api/documents/ingest",
        json={"title": "OCR lỗi", "source": str(stale), "content": stale.read_text(encoding="utf-8")},
    )
    assert stale_ingest.status_code == 200

    target.write_text(
        "Văn bản hợp nhất 80/VBHN-VPQH năm 2025 hợp nhất Luật Nghĩa vụ quân sự\n\n"
        "Điều 43. Điều kiện xuất ngũ.\n"
        "Hạ sĩ quan, binh sĩ đã hết thời hạn phục vụ tại ngũ thì được xuất ngũ.",
        encoding="utf-8",
    )
    reindexed = client.post("/api/documents/reindex")
    assert reindexed.status_code == 200
    assert reindexed.json() == {"documents_deleted": 2, "documents_ingested": 1}

    listed = client.get("/api/documents")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert "Điều kiện xuất ngũ" in listed.json()[0]["summary"]


def test_document_mutation_requires_admin_token_when_configured(client):
    client.app.state.services.settings.admin_token = "secret-token"

    denied = client.post(
        "/api/documents/ingest",
        json={
            "title": "Luật mẫu",
            "source": "manual-test",
            "content": "Luật Mẫu\n\nĐiều 1. Phạm vi điều chỉnh.\n1. Văn bản này dùng để test ingest.",
        },
    )
    assert denied.status_code == 401

    allowed = client.post(
        "/api/documents/ingest",
        headers={"X-Admin-Token": "secret-token"},
        json={
            "title": "Luật mẫu",
            "source": "manual-test",
            "content": "Luật Mẫu\n\nĐiều 1. Phạm vi điều chỉnh.\n1. Văn bản này dùng để test ingest.",
        },
    )
    assert allowed.status_code == 200
