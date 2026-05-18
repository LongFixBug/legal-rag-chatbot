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
from app.services.military import MilitaryQuestionType, MilitaryServiceLawService


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
        self.military_service_law_service = MilitaryServiceLawService()

    async def chat(self, question: str, top_k: int | None = None, conversation_id: str | None = None) -> ChatResponse:
        normalized_question = self.legal_text_service.normalize_query(question)
        conversation = await self._ensure_conversation(conversation_id=conversation_id, first_question=normalized_question)
        history_records = await self.metadata_store.list_chat_history(
            conversation.id,
            limit=self.settings.max_history_messages,
        )
        classification_context = " ".join(record.content for record in history_records[-2:] if record.role == "user")
        military_question_type = self.military_service_law_service.classify_question(
            f"{classification_context} {normalized_question}".strip()
        )

        if military_question_type == MilitaryQuestionType.non_military:
            answer = self.military_service_law_service.out_of_scope_answer()
            await self._store_turn(conversation.id, normalized_question, answer)
            return ChatResponse(
                conversation_id=conversation.id,
                answer=answer,
                citations=[],
                retrieved_chunks=0,
                history_used=len(history_records),
                confidence=0.0,
                abstained=True,
                validation_warnings=[],
            )

        limit = top_k or self.settings.top_k
        retrieved = await self._retrieve(normalized_question, limit, military_question_type=military_question_type)
        citations_source = self._relevant_military_citations(retrieved, military_question_type)
        confidence = self._retrieval_confidence(citations_source)
        if confidence < self.settings.min_retrieval_confidence:
            answer = self.military_service_law_service.abstain_answer()
            await self._store_turn(conversation.id, normalized_question, answer)
            return ChatResponse(
                conversation_id=conversation.id,
                answer=answer,
                citations=[],
                retrieved_chunks=0,
                history_used=len(history_records),
                confidence=confidence,
                abstained=True,
                validation_warnings=[],
            )

        answer = self.military_service_law_service.answer_question(
            normalized_question,
            retrieved,
            question_type=military_question_type,
        )
        if answer is None:
            history = [record.to_dict() for record in history_records]
            answer = await self.llm_service.answer(normalized_question, retrieved, history)

        validation_warnings = self.citation_service.validate_answer_citations(answer, retrieved)
        await self._store_turn(conversation.id, normalized_question, answer)
        citations = [self._to_citation_response(item) for item in citations_source]
        return ChatResponse(
            conversation_id=conversation.id,
            answer=answer,
            citations=citations,
            retrieved_chunks=len(citations_source),
            history_used=len(history_records),
            confidence=confidence,
            abstained=False,
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

    async def _store_turn(self, conversation_id: str, question: str, answer: str) -> None:
        await self.metadata_store.append_chat(ChatMessageRecord(conversation_id=conversation_id, role="user", content=question))
        await self.metadata_store.append_chat(ChatMessageRecord(conversation_id=conversation_id, role="assistant", content=answer))

    @staticmethod
    def _build_conversation_title(question: str, max_length: int = 60) -> str:
        compact = " ".join(question.split())
        return compact[: max_length - 3] + "..." if len(compact) > max_length else compact

    # ------------------------------------------------------------------ #
    # Retrieval pipeline
    # ------------------------------------------------------------------ #

    async def _retrieve(
        self,
        question: str,
        limit: int,
        article_filter: str | None = None,
        military_question_type: MilitaryQuestionType | None = None,
    ) -> list[dict]:
        question_type = military_question_type or self.military_service_law_service.classify_question(question)
        expanded_questions = self._expand_queries(question, question_type)

        all_results: list[dict] = []
        seen_ids: set[str] = set()
        for variant_question in expanded_questions:
            vector = await self.embedding_service.embed(variant_question)
            search_results = await self.vector_store.search(vector, limit=limit * 3, filters={"article": article_filter})
            for result in search_results:
                if result["id"] in seen_ids:
                    continue
                all_results.append(result)
                seen_ids.add(result["id"])

        merged_results = all_results[: limit * 5]
        article_refs = {ref for ref in self.citation_service.extract_references(question) if ref.startswith("Điều ")}
        article_refs = self._add_military_article_refs(question_type, article_refs)
        merged_results = await self._merge_exact_article_matches(merged_results, article_refs, question_type, article_filter)
        merged_results = await self._merge_military_service_matches(merged_results, question_type)
        merged_results = await self._merge_topical_title_matches(merged_results, question)
        reranked = self._rerank(merged_results, question, article_filter, article_refs, question_type)
        return reranked[:limit]

    @staticmethod
    def _expand_queries(question: str, question_type: MilitaryQuestionType) -> list[str]:
        variants = [question]
        if question_type != MilitaryQuestionType.non_military:
            variants.append(f"{question} luật nghĩa vụ quân sự nhập ngũ")
            if question_type in {MilitaryQuestionType.health, MilitaryQuestionType.eyesight}:
                variants.append(f"{question} Văn bản hợp nhất 88/VBHN-BQP khám sức khỏe nghĩa vụ quân sự")
            if question_type == MilitaryQuestionType.penalty:
                variants.append(f"{question} Văn bản hợp nhất 04/VBHN-BQP xử phạt nghĩa vụ quân sự")
        return variants[:3]

    def _add_military_article_refs(self, question_type: MilitaryQuestionType, article_refs: set[str]) -> set[str]:
        for article in self.military_service_law_service.suggested_articles(question_type):
            if article.startswith("Điều "):
                article_refs.add(article)
        return article_refs

    def _filter_military_citations(self, retrieved: list[dict], question_type: MilitaryQuestionType) -> list[dict]:
        filtered = self._relevant_military_citations(retrieved, question_type)
        return filtered or retrieved

    def _relevant_military_citations(self, retrieved: list[dict], question_type: MilitaryQuestionType) -> list[dict]:
        filtered = [
            item
            for item in retrieved
            if self.military_service_law_service.is_relevant_context(item, question_type)
        ]
        return filtered

    @staticmethod
    def _retrieval_confidence(retrieved: list[dict]) -> float:
        if not retrieved:
            return 0.0
        best_score = max(float(item.get("score", 0.0)) for item in retrieved)
        return round(max(0.0, min(best_score / 5.0, 1.0)), 4)

    # ------------------------------------------------------------------ #
    # Re-ranking
    # ------------------------------------------------------------------ #

    def _rerank(
        self,
        search_results: list[dict],
        question: str,
        article_filter: str | None,
        article_refs: set[str],
        question_type: MilitaryQuestionType,
    ) -> list[dict]:
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
                score += max(self.settings.article_reference_boost, 1.5)
            if payload.get("_exact_article_match"):
                score += 2.0
            if payload.get("_topical_title_match"):
                score += self.settings.title_match_boost + float(payload["_topical_title_match"])
            if payload.get("_military_service_match"):
                score += 1.5
            if self.military_service_law_service.is_relevant_context(payload, question_type):
                score += 1.75

            reranked.append({
                "id": item["id"],
                "score": round(score, 4),
                "document_id": payload["document_id"],
                "title": payload["title"],
                "article": payload.get("article"),
                "clause": payload.get("clause"),
                "content": payload["content"],
            })

        reranked.sort(key=lambda value: value["score"], reverse=True)
        return reranked

    # ------------------------------------------------------------------ #
    # Merge helpers
    # ------------------------------------------------------------------ #

    async def _merge_exact_article_matches(
        self,
        search_results: list[dict],
        article_refs: set[str],
        question_type: MilitaryQuestionType,
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
            candidate = {
                "title": document.title if document else chunk.document_id,
                "article": chunk.article,
                "content": chunk.content,
            }
            if (
                question_type != MilitaryQuestionType.non_military
                and not self.military_service_law_service.is_relevant_context(candidate, question_type)
            ):
                continue
            search_results.append(self._chunk_to_search_result(chunk, document, exact_article_match=True))
            known_ids.add(chunk.id)

        return search_results

    async def _merge_military_service_matches(
        self,
        search_results: list[dict],
        question_type: MilitaryQuestionType,
    ) -> list[dict]:
        if question_type == MilitaryQuestionType.non_military:
            return search_results
        known_ids = {item["id"] for item in search_results}
        documents = {item.id: item for item in await self.metadata_store.list_documents()}
        for chunk in await self.metadata_store.list_chunks():
            if chunk.id in known_ids:
                continue
            document = documents.get(chunk.document_id)
            item = {"title": document.title if document else chunk.document_id, "article": chunk.article, "content": chunk.content}
            if not self.military_service_law_service.is_relevant_context(item, question_type):
                continue
            search_results.append(self._chunk_to_search_result(chunk, document, military_service_match=True))
            known_ids.add(chunk.id)
        return search_results

    async def _merge_topical_title_matches(self, search_results: list[dict], question: str) -> list[dict]:
        known_ids = {item["id"] for item in search_results}
        documents = {item.id: item for item in await self.metadata_store.list_documents()}
        chunks = await self.metadata_store.list_chunks()
        chunks_by_document: dict[str, list] = {}
        for chunk in chunks:
            chunks_by_document.setdefault(chunk.document_id, []).append(chunk)

        for document in documents.values():
            title_score = self.legal_text_service.lexical_overlap(question, f"{document.title} {document.summary}")
            has_phrase_match = self.legal_text_service.has_phrase_overlap(question, f"{document.title} {document.summary}")
            if title_score < 0.5 and not has_phrase_match:
                continue

            best_chunk = max(
                chunks_by_document.get(document.id, []),
                key=lambda chunk: self.legal_text_service.lexical_overlap(
                    question,
                    f"{chunk.article or ''} {chunk.clause or ''} {chunk.content}",
                ),
                default=None,
            )
            if best_chunk is None or best_chunk.id in known_ids:
                continue
            search_results.append(
                self._chunk_to_search_result(
                    best_chunk,
                    document,
                    topical_title_match=round(max(title_score, 1.0 if has_phrase_match else 0.0), 4),
                )
            )
            known_ids.add(best_chunk.id)

        return search_results

    @staticmethod
    def _chunk_to_search_result(
        chunk,
        document,
        *,
        exact_article_match: bool = False,
        military_service_match: bool = False,
        topical_title_match: float | None = None,
    ) -> dict:
        payload = {
            "document_id": chunk.document_id,
            "title": document.title if document else chunk.document_id,
            "article": chunk.article,
            "clause": chunk.clause,
            "content": chunk.content,
            "citations": chunk.citations,
        }
        if exact_article_match:
            payload["_exact_article_match"] = True
        if military_service_match:
            payload["_military_service_match"] = True
        if topical_title_match is not None:
            payload["_topical_title_match"] = topical_title_match
        return {"id": chunk.id, "score": 0.0, "payload": payload}

    # ------------------------------------------------------------------ #
    # Citation formatting
    # ------------------------------------------------------------------ #

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
