from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PRELOAD_SAMPLE_DATA", "false")
    monkeypatch.setenv("PRELOAD_INCLUDE_PATTERN", "*")
    get_settings.cache_clear()

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "sample.txt").write_text(
        "Luật Doanh nghiệp 2020\n\nĐiều 17. Quyền thành lập doanh nghiệp.\n1. Tổ chức, cá nhân có quyền thành lập và quản lý doanh nghiệp tại Việt Nam, trừ trường hợp pháp luật cấm.",
        encoding="utf-8",
    )

    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()
