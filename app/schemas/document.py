from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentIngestRequest(BaseModel):
    title: str = Field(min_length=3)
    content: str = Field(min_length=20)
    doc_type: str = "legal_text"
    source: str = "manual"


class DocumentResponse(BaseModel):
    id: str
    title: str
    source: str
    doc_type: str
    summary: str
    created_at: str
    metadata: dict


class DocumentIngestResponse(BaseModel):
    document: DocumentResponse
    chunks_indexed: int
