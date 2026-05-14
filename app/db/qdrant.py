from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from qdrant_client import AsyncQdrantClient, models as qmodels

from app.db.interfaces import VectorStore


class LocalVectorStore(VectorStore):
    def __init__(self, storage_dir: Path):
        self._path = storage_dir / "vectors.json"
        if not self._path.exists():
            self._write([])

    async def init(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def _read(self) -> list[dict[str, Any]]:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write(self, payload: list[dict[str, Any]]) -> None:
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    async def upsert(self, point_id: str, vector: list[float], payload: dict[str, Any]) -> None:
        points = [point for point in self._read() if point["id"] != point_id]
        points.append({"id": point_id, "vector": vector, "payload": payload})
        self._write(points)

    async def delete_by_document(self, document_id: str) -> None:
        points = [point for point in self._read() if point["payload"].get("document_id") != document_id]
        self._write(points)

    async def search(
        self,
        query_vector: list[float],
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        results: list[dict[str, Any]] = []
        for point in self._read():
            payload = point["payload"]
            if not all(payload.get(key) == value for key, value in filters.items() if value is not None):
                continue
            score = self._cosine(query_vector, point["vector"])
            results.append({"id": point["id"], "score": score, "payload": payload})
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)


class QdrantVectorStore(VectorStore):
    def __init__(self, url: str, collection_name: str, dimension: int):
        self.client = AsyncQdrantClient(url=url)
        self.collection_name = collection_name
        self.dimension = dimension

    async def init(self) -> None:
        if not await self.client.collection_exists(self.collection_name):
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(size=self.dimension, distance=qmodels.Distance.COSINE),
            )

    async def close(self) -> None:
        await self.client.close()

    async def upsert(self, point_id: str, vector: list[float], payload: dict[str, Any]) -> None:
        await self.client.upsert(
            collection_name=self.collection_name,
            points=[qmodels.PointStruct(id=point_id, vector=vector, payload=payload)],
        )

    async def delete_by_document(self, document_id: str) -> None:
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[qmodels.FieldCondition(key="document_id", match=qmodels.MatchValue(value=document_id))]
                )
            ),
        )

    async def search(
        self,
        query_vector: list[float],
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[qmodels.FieldCondition] = []
        for key, value in (filters or {}).items():
            if value is not None:
                conditions.append(qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value)))
        response = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            query_filter=qmodels.Filter(must=conditions) if conditions else None,
            with_payload=True,
        )
        return [
            {"id": str(hit.id), "score": float(hit.score), "payload": dict(hit.payload or {})}
            for hit in response.points
        ]
