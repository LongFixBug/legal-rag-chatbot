from __future__ import annotations

import hashlib
import math
from typing import Protocol

import httpx

from app.config import Settings


class EmbeddingService(Protocol):
    async def embed(self, text: str) -> list[float]: ...


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


class OpenAICompatibleEmbeddingService:
    def __init__(self, settings: Settings, fallback: EmbeddingService | None = None):
        self.base_url = self._normalize_base_url(settings.resolved_embedding_base_url)
        self.api_key = settings.resolved_embedding_api_key
        self.model = settings.resolved_embedding_model
        self.fallback = fallback

    async def embed(self, text: str) -> list[float]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json={"model": self.model, "input": text},
                )
                response.raise_for_status()
                payload = response.json()
                return payload["data"][0]["embedding"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError):
            if self.fallback is None:
                raise
            return await self.fallback.embed(text)

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        base = base_url.rstrip("/")
        return base if base.endswith("/v1") else f"{base}/v1"



def build_embedding_service(settings: Settings) -> EmbeddingService:
    fallback = LocalHashEmbeddingService(settings.embedding_dimension)
    if settings.resolved_embedding_base_url and settings.resolved_embedding_model:
        return OpenAICompatibleEmbeddingService(settings, fallback=fallback)
    return fallback
