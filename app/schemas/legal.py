from __future__ import annotations

from pydantic import BaseModel


class LegalSearchResponseItem(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    article: str | None
    clause: str | None
    excerpt: str
    score: float


class LegalSearchResponse(BaseModel):
    query: str
    article_filter: str | None
    results: list[LegalSearchResponseItem]
