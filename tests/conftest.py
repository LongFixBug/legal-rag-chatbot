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
        "Văn bản hợp nhất 80/VBHN-VPQH năm 2025 hợp nhất Luật Nghĩa vụ quân sự\n\n"
        "Điều 30. Độ tuổi gọi nhập ngũ.\n"
        "Công dân đủ 18 tuổi được gọi nhập ngũ; độ tuổi gọi nhập ngũ từ đủ 18 tuổi đến hết 25 tuổi; "
        "công dân được đào tạo trình độ cao đẳng, đại học đã được tạm hoãn gọi nhập ngũ thì độ tuổi gọi nhập ngũ đến hết 27 tuổi.\n\n"
        "Điều 41. Tạm hoãn gọi nhập ngũ và miễn gọi nhập ngũ.\n"
        "Đang học đại học hệ chính quy trong thời gian một khóa đào tạo của một trình độ đào tạo thì được tạm hoãn gọi nhập ngũ.",
        encoding="utf-8",
    )

    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()
