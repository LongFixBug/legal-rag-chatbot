from __future__ import annotations

import uuid

from app.config import Settings
from app.db.interfaces import MetadataStore, VectorStore
from app.db.models import ChatMessageRecord, ConversationRecord
from app.schemas.chat import ChatResponse, CitationResponse
from app.schemas.legal import LegalSearchResponse, LegalSearchResponseItem
from app.services.citation import CitationService
from app.services.embedding import EmbeddingService
from app.services.legal import LegalTextService
from app.services.llm import LLMService


class RagService:
    def __init__(
        self,
        settings: Settings,
        metadata_store: MetadataStore,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        llm_service: LLMService,
        citation_service: CitationService,
        legal_text_service: LegalTextService,
    ):
        self.settings = settings
        self.metadata_store = metadata_store
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self.citation_service = citation_service
        self.legal_text_service = legal_text_service

    async def chat(self, question: str, top_k: int | None = None, conversation_id: str | None = None) -> ChatResponse:
        normalized_question = self.legal_text_service.normalize_query(question)
        conversation = await self._ensure_conversation(conversation_id=conversation_id, first_question=normalized_question)
        limit = top_k or self.settings.top_k
        history_records = await self.metadata_store.list_chat_history(conversation.id, limit=self.settings.max_history_messages)
        history = [record.to_dict() for record in history_records]
        retrieved = await self._retrieve(normalized_question, limit)
        answer = await self.llm_service.answer(normalized_question, retrieved, history)
        validation_warnings = self.citation_service.validate_answer_citations(answer, retrieved)
        await self.metadata_store.append_chat(
            ChatMessageRecord(conversation_id=conversation.id, role="user", content=normalized_question)
        )
        await self.metadata_store.append_chat(
            ChatMessageRecord(conversation_id=conversation.id, role="assistant", content=answer)
        )
        citations = [self._to_citation_response(item) for item in retrieved]
        return ChatResponse(
            conversation_id=conversation.id,
            answer=answer,
            citations=citations,
            retrieved_chunks=len(retrieved),
            history_used=len(history),
            validation_warnings=validation_warnings,
        )

    async def create_conversation(self, title: str | None = None) -> ConversationRecord:
        conversation = ConversationRecord(
            id=str(uuid.uuid4()),
            title=title or "Cuộc trò chuyện mới",
        )
        await self.metadata_store.create_conversation(conversation)
        return conversation

    async def list_conversations(self) -> list[ConversationRecord]:
        return await self.metadata_store.list_conversations(limit=50)

    async def get_conversation_history(self, conversation_id: str) -> list[ChatMessageRecord] | None:
        conversation = await self.metadata_store.get_conversation(conversation_id)
        if conversation is None:
            return None
        return await self.metadata_store.list_chat_history(conversation_id)

    async def delete_conversation(self, conversation_id: str) -> bool:
        conversation = await self.metadata_store.get_conversation(conversation_id)
        if conversation is None:
            return False
        await self.metadata_store.delete_conversation(conversation_id)
        return True

    async def legal_search(self, query: str, article_filter: str | None = None, top_k: int | None = None) -> LegalSearchResponse:
        normalized_query = self.legal_text_service.normalize_query(query)
        retrieved = await self._retrieve(normalized_query, top_k or self.settings.top_k * 2, article_filter)
        return LegalSearchResponse(
            query=normalized_query,
            article_filter=article_filter,
            results=[
                LegalSearchResponseItem(
                    chunk_id=item["id"],
                    document_id=item["document_id"],
                    title=item["title"],
                    article=item.get("article"),
                    clause=item.get("clause"),
                    excerpt=item["content"],
                    score=item["score"],
                )
                for item in retrieved
            ],
        )

    async def _ensure_conversation(self, conversation_id: str | None, first_question: str) -> ConversationRecord:
        if conversation_id:
            conversation = await self.metadata_store.get_conversation(conversation_id)
            if conversation is not None:
                return conversation
        title = self._build_conversation_title(first_question)
        conversation = ConversationRecord(id=str(uuid.uuid4()), title=title)
        await self.metadata_store.create_conversation(conversation)
        return conversation

    @staticmethod
    def _build_conversation_title(question: str, max_length: int = 60) -> str:
        compact = " ".join(question.split())
        return compact[: max_length - 3] + "..." if len(compact) > max_length else compact

    async def _retrieve(self, question: str, limit: int, article_filter: str | None = None) -> list[dict]:
        vector = await self.embedding_service.embed(question)
        search_results = await self.vector_store.search(vector, limit=limit * 3, filters={"article": article_filter})
        article_refs = {ref for ref in self.citation_service.extract_references(question) if ref.startswith("Điều ")}
        search_results = await self._merge_exact_article_matches(search_results, article_refs, article_filter)
        reranked: list[dict] = []
        for item in search_results:
            payload = item["payload"]
            vector_score = float(item["score"])
            lexical_score = self.legal_text_service.lexical_overlap(
                question,
                f"{payload.get('title', '')} {payload.get('article') or ''} {payload.get('content', '')}",
            )
            score = ((1 - self.settings.lexical_weight) * vector_score) + (self.settings.lexical_weight * lexical_score)
            if article_filter and payload.get("article") == article_filter:
                score += 0.5
            if article_refs and payload.get("article") in article_refs:
                score += self.settings.article_reference_boost
            if payload.get("_exact_article_match"):
                score += self.settings.article_reference_boost
            if payload.get("title") and any(token in payload["title"].lower() for token in question.lower().split() if len(token) > 3):
                score += self.settings.title_match_boost
            reranked.append(
                {
                    "id": item["id"],
                    "score": round(score, 4),
                    "document_id": payload["document_id"],
                    "title": payload["title"],
                    "article": payload.get("article"),
                    "clause": payload.get("clause"),
                    "content": payload["content"],
                }
            )
        reranked.sort(key=lambda value: value["score"], reverse=True)
        return reranked[:limit]

    async def _merge_exact_article_matches(
        self,
        search_results: list[dict],
        article_refs: set[str],
        article_filter: str | None = None,
    ) -> list[dict]:
        target_articles = set(article_refs)
        if article_filter:
            target_articles.add(article_filter)
        if not target_articles:
            return search_results

        known_ids = {item["id"] for item in search_results}
        documents = {item.id: item for item in await self.metadata_store.list_documents()}
        chunks = await self.metadata_store.list_chunks()

        for chunk in chunks:
            if chunk.article not in target_articles or chunk.id in known_ids:
                continue
            document = documents.get(chunk.document_id)
            search_results.append(
                {
                    "id": chunk.id,
                    "score": 0.0,
                    "payload": {
                        "document_id": chunk.document_id,
                        "title": document.title if document else chunk.document_id,
                        "article": chunk.article,
                        "clause": chunk.clause,
                        "content": chunk.content,
                        "citations": chunk.citations,
                        "_exact_article_match": True,
                    },
                }
            )
            known_ids.add(chunk.id)

        return search_results

    @staticmethod
    def _to_citation_response(item: dict) -> CitationResponse:
        excerpt = " ".join(item["content"].split())
        excerpt = excerpt[:240] + "..." if len(excerpt) > 240 else excerpt
        return CitationResponse(
            chunk_id=item["id"],
            document_id=item["document_id"],
            title=item["title"],
            article=item.get("article"),
            clause=item.get("clause"),
            excerpt=excerpt,
            score=item["score"],
        )
