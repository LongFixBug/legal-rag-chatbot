import httpx
import pytest

from app.config import Settings
from app.services.embedding import LocalHashEmbeddingService, OpenAICompatibleEmbeddingService
from app.services.llm import ExtractiveLLMService, OpenAICompatibleLLMService


@pytest.mark.asyncio
async def test_llm_service_retries_then_falls_back(monkeypatch: pytest.MonkeyPatch):
    attempts = {"count": 0}

    async def fake_post(self, *args, **kwargs):
        attempts["count"] += 1
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    settings = Settings(
        llm_base_url="http://127.0.0.1:8080",
        llm_model="demo-llm",
        llm_timeout_seconds=0.01,
        llm_max_retries=2,
    )
    service = OpenAICompatibleLLMService(settings, fallback=ExtractiveLLMService())

    answer = await service.answer(
        "Điều 1 nói gì?",
        [{"title": "Luật mẫu", "article": "Điều 1", "content": "Điều 1. Nội dung mẫu."}],
        [],
    )

    assert attempts["count"] == 3
    assert "Dựa trên các văn bản đã nạp" in answer


@pytest.mark.asyncio
async def test_embedding_service_retries_then_falls_back(monkeypatch: pytest.MonkeyPatch):
    attempts = {"count": 0}

    async def fake_post(self, *args, **kwargs):
        attempts["count"] += 1
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    settings = Settings(
        embedding_base_url="http://127.0.0.1:8081",
        embedding_model="demo-embed",
        embedding_timeout_seconds=0.01,
        embedding_max_retries=1,
    )
    fallback = LocalHashEmbeddingService(settings.embedding_dimension)
    service = OpenAICompatibleEmbeddingService(settings, fallback=fallback)

    vector = await service.embed("Điều 17 doanh nghiệp")

    assert attempts["count"] == 2
    assert len(vector) == settings.embedding_dimension
