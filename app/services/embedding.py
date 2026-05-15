from __future__ import annotations

import hashlib
import math
from typing import Protocol

import httpx

from app.config import Settings


class EmbeddingService(Protocol):
    async def embed(self, text: str) -> list[float]: ...

    async def health_check(self) -> dict[str, object]: ...


class LocalHashEmbeddingService:
    def __init__(self, dimension: int):
        self.dimension = dimension

    async def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = [token for token in text.lower().split() if token]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for index in range(0, min(len(digest), self.dimension)):
                bucket = index % self.dimension
                value = digest[index] / 255.0
                vector[bucket] += value if index % 2 == 0 else -value
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    async def health_check(self) -> dict[str, object]:
        return {"ready": True, "operational": True, "mode": "local_fallback", "dimension": self.dimension}


class OpenAICompatibleEmbeddingService:
    def __init__(self, settings: Settings, fallback: EmbeddingService | None = None):
        self.base_url = self._normalize_base_url(settings.resolved_embedding_base_url)
        self.api_key = settings.resolved_embedding_api_key
        self.model = settings.resolved_embedding_model
        self.timeout = settings.embedding_timeout_seconds
        self.max_retries = settings.embedding_max_retries
        self.fallback = fallback

    async def embed(self, text: str) -> list[float]:
        try:
            payload = await self._post_json("/embeddings", {"model": self.model, "input": text})
            return payload["data"][0]["embedding"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError):
            if self.fallback is None:
                raise
            return await self.fallback.embed(text)

    async def health_check(self) -> dict[str, object]:
        try:
            payload = await self._get_json("/models")
            models = [item.get("id") for item in payload.get("data", []) if isinstance(item, dict)]
            model_ready = not models or self.model in models
            result: dict[str, object] = {
                "ready": model_ready,
                "operational": model_ready or self.fallback is not None,
                "mode": "remote",
                "base_url": self.base_url,
                "model": self.model,
                "fallback_available": self.fallback is not None,
            }
            if not model_ready:
                result["error"] = f"Configured model '{self.model}' not exposed by remote embedding server"
                if self.fallback is not None:
                    result["degraded_reason"] = "Using fallback embedding service because the configured remote model is unavailable"
            return result
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            return {
                "ready": False,
                "operational": self.fallback is not None,
                "mode": "remote",
                "base_url": self.base_url,
                "model": self.model,
                "fallback_available": self.fallback is not None,
                "error": str(exc),
                "degraded_reason": "Using fallback embedding service because the remote embedding health check failed"
                if self.fallback is not None
                else "Remote embedding health check failed",
            }

    async def _post_json(self, path: str, payload: dict) -> dict:
        last_error: Exception | None = None
        for _ in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}{path}",
                        headers=self._headers(),
                        json=payload,
                    )
                    response.raise_for_status()
                    return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    async def _get_json(self, path: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}{path}", headers=self._headers())
            response.raise_for_status()
            return response.json()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        base = base_url.rstrip("/")
        return base if base.endswith("/v1") else f"{base}/v1"



def build_embedding_service(settings: Settings) -> EmbeddingService:
    fallback = LocalHashEmbeddingService(settings.embedding_dimension)
    if settings.resolved_embedding_base_url and settings.resolved_embedding_model:
        return OpenAICompatibleEmbeddingService(settings, fallback=fallback)
    return fallback
