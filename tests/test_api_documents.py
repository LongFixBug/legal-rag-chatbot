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


def test_ingest_reuses_existing_document_for_same_content(client):
    payload = {
        "title": "Luật chống trùng",
        "source": "manual-duplicate-test",
        "content": "Luật Chống Trùng\n\nĐiều 1. Phạm vi điều chỉnh.\n1. Văn bản này dùng để test chống ingest trùng.",
    }

    first = client.post("/api/documents/ingest", json=payload)
    assert first.status_code == 200
    second = client.post("/api/documents/ingest", json=payload)
    assert second.status_code == 200

    assert second.json()["document"]["id"] == first.json()["document"]["id"]
    listed = client.get("/api/documents")
    assert listed.status_code == 200
    matching = [item for item in listed.json() if item["source"] == payload["source"]]
    assert len(matching) == 1


def test_ingested_document_records_identity_and_version_metadata(client):
    response = client.post(
        "/api/documents/ingest",
        json={
            "title": "Luật metadata",
            "source": "manual-metadata-test",
            "content": "Luật Metadata\n\nĐiều 1. Phạm vi điều chỉnh.\n1. Văn bản này dùng để test metadata.",
        },
    )
    assert response.status_code == 200
    metadata = response.json()["document"]["metadata"]

    assert metadata["content_sha256"]
    assert metadata["identity_key"].startswith("sha256:")
    assert metadata["parser_version"]
    assert metadata["chunking_version"]
    assert metadata["embedding_dimension"] == client.app.state.services.settings.embedding_dimension
    assert metadata["qdrant_collection"] == client.app.state.services.settings.qdrant_collection


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


def test_upload_rejects_files_over_configured_size(client):
    client.app.state.services.settings.max_upload_bytes = 16

    response = client.post(
        "/api/documents/upload",
        data={"title": "Luật quá lớn"},
        files={"file": ("large.txt", b"x" * 32, "text/plain")},
    )

    assert response.status_code == 413
    assert "File too large" in response.json()["detail"]


def test_upload_rejects_unsupported_file_extension(client):
    response = client.post(
        "/api/documents/upload",
        data={"title": "File không hợp lệ"},
        files={"file": ("malware.exe", b"not a legal document", "application/octet-stream")},
    )

    assert response.status_code == 415
    assert "Unsupported file type" in response.json()["detail"]


def test_document_mutation_is_rate_limited_when_configured(client):
    client.app.state.services.settings.document_mutation_rate_limit_per_minute = 1

    first = client.post(
        "/api/documents/ingest",
        json={
            "title": "Luật mẫu 1",
            "source": "manual-test-1",
            "content": "Luật Mẫu 1\n\nĐiều 1. Phạm vi điều chỉnh.\n1. Văn bản này dùng để test ingest.",
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/documents/ingest",
        json={
            "title": "Luật mẫu 2",
            "source": "manual-test-2",
            "content": "Luật Mẫu 2\n\nĐiều 1. Phạm vi điều chỉnh.\n1. Văn bản này dùng để test ingest.",
        },
    )
    assert second.status_code == 429
    assert "Rate limit exceeded" in second.json()["detail"]


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
