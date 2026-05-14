from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=3)
    top_k: int | None = Field(default=None, ge=1, le=10)
    conversation_id: str | None = None


class CitationResponse(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    article: str | None = None
    clause: str | None = None
    excerpt: str
    score: float


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    citations: list[CitationResponse]
    retrieved_chunks: int
    history_used: int = 0
    validation_warnings: list[str] = Field(default_factory=list)


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    metadata: dict = Field(default_factory=dict)


class ConversationHistoryMessageResponse(BaseModel):
    conversation_id: str
    role: str
    content: str
    created_at: str


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1)
