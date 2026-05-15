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
from app.services.tax import TaxComputationService, TaxQuestionType


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
        self.tax_computation_service = TaxComputationService()

    async def chat(self, question: str, top_k: int | None = None, conversation_id: str | None = None) -> ChatResponse:
        normalized_question = self.legal_text_service.normalize_query(question)
        conversation = await self._ensure_conversation(conversation_id=conversation_id, first_question=normalized_question)
        limit = top_k or self.settings.top_k
        history_records = await self.metadata_store.list_chat_history(conversation.id, limit=self.settings.max_history_messages)
        history = [record.to_dict() for record in history_records]
        retrieved = await self._retrieve(normalized_question, limit)
        answer = self.tax_computation_service.answer_tax_question(normalized_question, retrieved)
        question_type = self.tax_computation_service.classify_question(normalized_question)
        citations_source = self._filter_tax_retrieved_items(retrieved, question_type, answer is not None)
        if answer is None:
            answer = await self.llm_service.answer(normalized_question, retrieved, history)
        validation_warnings = self.citation_service.validate_answer_citations(answer, retrieved)
        await self.metadata_store.append_chat(
            ChatMessageRecord(conversation_id=conversation.id, role="user", content=normalized_question)
        )
        await self.metadata_store.append_chat(
            ChatMessageRecord(conversation_id=conversation.id, role="assistant", content=answer)
        )
        citations = [self._to_citation_response(item) for item in citations_source]
        return ChatResponse(
            conversation_id=conversation.id,
            answer=answer,
            citations=citations,
            retrieved_chunks=len(citations_source),
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

    # ------------------------------------------------------------------ #
    #  Retrieval pipeline
    # ------------------------------------------------------------------ #

    async def _retrieve(self, question: str, limit: int, article_filter: str | None = None) -> list[dict]:
        question_type = self.tax_computation_service.classify_question(question)
        expanded_questions = self._expand_queries(question, question_type)

        all_results: list[dict] = []
        seen_ids: set[str] = set()
        for variant_question in expanded_questions:
            vector = await self.embedding_service.embed(variant_question)
            search_results = await self.vector_store.search(vector, limit=limit * 3, filters={"article": article_filter})
            for result in search_results:
                if result["id"] not in seen_ids:
                    all_results.append(result)
                    seen_ids.add(result["id"])

        merged_results = all_results[: limit * 5]

        article_refs = {ref for ref in self.citation_service.extract_references(question) if ref.startswith("Điều ")}
        article_refs = self._add_tax_article_refs(question_type, article_refs)

        merged_results = await self._merge_exact_article_matches(merged_results, article_refs, question_type, article_filter)
        merged_results = await self._merge_prize_winning_matches(merged_results, question_type)
        merged_results = await self._merge_family_deduction_matches(merged_results, question_type)
        merged_results = await self._merge_inheritance_gift_matches(merged_results, question_type)
        merged_results = await self._merge_disability_tax_matches(merged_results, question_type)
        merged_results = await self._merge_tax_liability_matches(merged_results, question_type)
        merged_results = await self._merge_topical_title_matches(merged_results, question)

        reranked = self._rerank(merged_results, question, article_filter, article_refs, question_type)
        selected = reranked[:limit]
        if question_type == TaxQuestionType.prize_winning:
            selected = self._ensure_prize_threshold_coverage(selected, reranked, limit)
        return selected

    @staticmethod
    def _expand_queries(question: str, question_type: TaxQuestionType) -> list[str]:
        variants = [question]
        folded = question.lower()
        if question_type == TaxQuestionType.non_tax and not any(term in folded for term in ("điều", "dieu", "quy định")):
            variants.append(f"quy định pháp luật về {question}")
        if question_type != TaxQuestionType.non_tax and "thue" not in folded:
            variants.append(f"{question} thuế TNCN")
        if question_type == TaxQuestionType.general_tax:
            variants.append(f"{question} theo Luật Thuế thu nhập cá nhân 109/2025/QH15")
        return variants[:3]

    @staticmethod
    def _add_tax_article_refs(question_type: TaxQuestionType, article_refs: set[str]) -> set[str]:
        if question_type == TaxQuestionType.family_deduction:
            article_refs.add("Điều 10")
        elif question_type == TaxQuestionType.inheritance_gift:
            article_refs.add("Điều 18")
        elif question_type == TaxQuestionType.disability_tax:
            article_refs.add("Điều 5")
            article_refs.add("Điều 10")
        elif question_type == TaxQuestionType.tax_liability:
            article_refs.update({"Điều 2", "Điều 3", "Điều 8", "Điều 10", "Điều 21"})
        return article_refs

    # ------------------------------------------------------------------ #
    #  Filtering retrieved items for citation display
    # ------------------------------------------------------------------ #

    def _filter_tax_retrieved_items(self, retrieved: list[dict], question_type: TaxQuestionType, answered_by_tax_service: bool) -> list[dict]:
        if not answered_by_tax_service:
            return retrieved

        if question_type == TaxQuestionType.inheritance_gift:
            filtered = [item for item in retrieved if self._has_folded_term(item, ("thua ke", "qua tang"))]
            return filtered or retrieved

        if question_type == TaxQuestionType.prize_winning:
            filtered = [item for item in retrieved if self._has_folded_term(item, ("trung thuong",))]
            return filtered or retrieved

        if question_type == TaxQuestionType.family_deduction:
            filtered = [item for item in retrieved if self._has_folded_term(item, ("giam tru gia canh",))]
            return filtered or retrieved

        if question_type == TaxQuestionType.disability_tax:
            filtered = [item for item in retrieved if self._is_disability_tax_context(item)]
            return filtered or retrieved

        if question_type == TaxQuestionType.tax_liability:
            filtered = [item for item in retrieved if self._is_tax_liability_context(item)]
            return filtered or retrieved

        return retrieved

    def _has_folded_term(self, item: dict, terms: tuple[str, ...]) -> bool:
        searchable = f"{item.get('title', '')} {item.get('article') or ''} {item.get('content', '')}"
        folded = self.legal_text_service._fold_text(searchable)
        return any(term in folded for term in terms)

    # ------------------------------------------------------------------ #
    #  Re-ranking
    # ------------------------------------------------------------------ #

    def _rerank(
        self,
        search_results: list[dict],
        question: str,
        article_filter: str | None,
        article_refs: set[str],
        question_type: TaxQuestionType,
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
            if payload.get("title") and any(token in payload["title"].lower() for token in question.lower().split() if len(token) > 3):
                score += self.settings.title_match_boost
            if payload.get("_topical_title_match"):
                score += self.settings.title_match_boost + float(payload["_topical_title_match"])

            for flag, boost in (("_prize_winning_match", 1.0), ("_family_deduction_match", 1.5),
                                ("_inheritance_gift_match", 1.5), ("_disability_tax_match", 1.5),
                                ("_tax_liability_match", 1.5)):
                if payload.get(flag):
                    score += boost

            if question_type == TaxQuestionType.tax_liability and self._is_tax_liability_context(payload):
                score += 1.5
                if payload.get("article") == "Điều 2":
                    score += 2.0
                if "Luật Thuế thu nhập cá nhân 109/2025/QH15" in payload.get("title", ""):
                    score += 0.5

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
    #  Merge helpers — exact article, topical title, domain signals
    # ------------------------------------------------------------------ #

    async def _merge_exact_article_matches(
        self, search_results: list[dict], article_refs: set[str],
        question_type: TaxQuestionType, article_filter: str | None = None,
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
            searchable_text = self.legal_text_service._fold_text(
                f"{document.title if document else ''} {chunk.article or ''} {chunk.content}"
            )

            if question_type == TaxQuestionType.inheritance_gift:
                if chunk.article == "Điều 18" and "thua ke" not in searchable_text and "qua tang" not in searchable_text:
                    continue
            if question_type == TaxQuestionType.prize_winning:
                if chunk.article == "Điều 25" and "trung thuong" not in searchable_text:
                    continue
            if question_type == TaxQuestionType.disability_tax:
                if chunk.article == "Điều 5" and "giam thue" not in searchable_text:
                    continue
                if chunk.article == "Điều 10" and "khuyet tat" not in searchable_text and "tan tat" not in searchable_text:
                    continue
            if question_type == TaxQuestionType.tax_liability:
                candidate = {
                    "title": document.title if document else chunk.document_id,
                    "article": chunk.article,
                    "content": chunk.content,
                }
                if not self._is_tax_liability_context(candidate):
                    continue

            search_results.append({
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
            })
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
                    question, f"{chunk.article or ''} {chunk.clause or ''} {chunk.content}",
                ),
                default=None,
            )
            if best_chunk is None or best_chunk.id in known_ids:
                continue

            search_results.append({
                "id": best_chunk.id,
                "score": 0.0,
                "payload": {
                    "document_id": best_chunk.document_id,
                    "title": document.title,
                    "article": best_chunk.article,
                    "clause": best_chunk.clause,
                    "content": best_chunk.content,
                    "citations": best_chunk.citations,
                    "_topical_title_match": round(max(title_score, 1.0 if has_phrase_match else 0.0), 4),
                },
            })
            known_ids.add(best_chunk.id)

        return search_results

    # ------------------------------------------------------------------ #
    #  Domain merge signals
    # ------------------------------------------------------------------ #

    async def _merge_prize_winning_matches(self, search_results: list[dict], question_type: TaxQuestionType) -> list[dict]:
        if question_type != TaxQuestionType.prize_winning:
            return search_results
        return await self._merge_by_content_signal(search_results, content_terms=("trung thuong",), flag="_prize_winning_match")

    async def _merge_family_deduction_matches(self, search_results: list[dict], question_type: TaxQuestionType) -> list[dict]:
        if question_type != TaxQuestionType.family_deduction:
            return search_results
        return await self._merge_by_folded_signal(search_results, required_text="giam tru gia canh", flag="_family_deduction_match")

    async def _merge_inheritance_gift_matches(self, search_results: list[dict], question_type: TaxQuestionType) -> list[dict]:
        if question_type != TaxQuestionType.inheritance_gift:
            return search_results
        return await self._merge_by_content_signal(search_results, content_terms=("thua ke", "qua tang"), flag="_inheritance_gift_match")

    async def _merge_disability_tax_matches(self, search_results: list[dict], question_type: TaxQuestionType) -> list[dict]:
        if question_type != TaxQuestionType.disability_tax:
            return search_results
        known_ids = {item["id"] for item in search_results}
        documents = {item.id: item for item in await self.metadata_store.list_documents()}
        for chunk in await self.metadata_store.list_chunks():
            if chunk.id in known_ids:
                continue
            document = documents.get(chunk.document_id)
            item = {"title": document.title if document else chunk.document_id, "article": chunk.article, "content": chunk.content}
            if not self._is_disability_tax_context(item):
                continue
            search_results.append({
                "id": chunk.id, "score": 0.0,
                "payload": {
                    "document_id": chunk.document_id,
                    "title": document.title if document else chunk.document_id,
                    "article": chunk.article, "clause": chunk.clause,
                    "content": chunk.content, "citations": chunk.citations,
                    "_disability_tax_match": True,
                },
            })
            known_ids.add(chunk.id)
        return search_results

    async def _merge_tax_liability_matches(self, search_results: list[dict], question_type: TaxQuestionType) -> list[dict]:
        if question_type != TaxQuestionType.tax_liability:
            return search_results
        known_ids = {item["id"] for item in search_results}
        documents = {item.id: item for item in await self.metadata_store.list_documents()}
        for chunk in await self.metadata_store.list_chunks():
            if chunk.id in known_ids:
                continue
            document = documents.get(chunk.document_id)
            item = {"title": document.title if document else chunk.document_id, "article": chunk.article, "content": chunk.content}
            if not self._is_tax_liability_context(item):
                continue
            search_results.append({
                "id": chunk.id, "score": 0.0,
                "payload": {
                    "document_id": chunk.document_id,
                    "title": document.title if document else chunk.document_id,
                    "article": chunk.article, "clause": chunk.clause,
                    "content": chunk.content, "citations": chunk.citations,
                    "_tax_liability_match": True,
                },
            })
            known_ids.add(chunk.id)
        return search_results

    async def _merge_by_content_signal(self, search_results: list[dict], content_terms: tuple[str, ...], flag: str) -> list[dict]:
        known_ids = {item["id"] for item in search_results}
        documents = {item.id: item for item in await self.metadata_store.list_documents()}
        for chunk in await self.metadata_store.list_chunks():
            if chunk.id in known_ids:
                continue
            searchable = f"{chunk.article or ''} {chunk.content}"
            tokens = self.legal_text_service.tokenize(searchable)
            if not self.legal_text_service.tokenize(" ".join(content_terms)).intersection(tokens):
                continue
            document = documents.get(chunk.document_id)
            search_results.append({
                "id": chunk.id, "score": 0.0,
                "payload": {
                    "document_id": chunk.document_id,
                    "title": document.title if document else chunk.document_id,
                    "article": chunk.article, "clause": chunk.clause,
                    "content": chunk.content, "citations": chunk.citations,
                    flag: True,
                },
            })
            known_ids.add(chunk.id)
        return search_results

    async def _merge_by_folded_signal(self, search_results: list[dict], required_text: str, flag: str) -> list[dict]:
        known_ids = {item["id"] for item in search_results}
        documents = {item.id: item for item in await self.metadata_store.list_documents()}
        for chunk in await self.metadata_store.list_chunks():
            if chunk.id in known_ids:
                continue
            searchable = f"{chunk.article or ''} {chunk.content}"
            if required_text not in self.legal_text_service._fold_text(searchable):
                continue
            document = documents.get(chunk.document_id)
            search_results.append({
                "id": chunk.id, "score": 0.0,
                "payload": {
                    "document_id": chunk.document_id,
                    "title": document.title if document else chunk.document_id,
                    "article": chunk.article, "clause": chunk.clause,
                    "content": chunk.content, "citations": chunk.citations,
                    flag: True,
                },
            })
            known_ids.add(chunk.id)
        return search_results

    # ------------------------------------------------------------------ #
    #  Context classifiers
    # ------------------------------------------------------------------ #

    def _is_disability_tax_context(self, item: dict) -> bool:
        folded = self.legal_text_service._fold_text(
            f"{item.get('title', '')} {item.get('article') or ''} {item.get('content', '')}"
        )
        has_disability = "khuyet tat" in folded or "tan tat" in folded
        has_tax_reduction = "giam thue" in folded and any(term in folded for term in ("tai nan", "benh hiem ngheo", "thien tai", "hoa hoan"))
        has_exempt_compensation = "tro cap" in folded and any(term in folded for term in ("tai nan lao dong", "benh nghe nghiep"))
        has_dependent_relief = "nguoi phu thuoc" in folded and any(term in folded for term in ("khuyet tat", "tan tat"))
        return has_disability or has_tax_reduction or has_exempt_compensation or has_dependent_relief

    def _is_tax_liability_context(self, item: dict) -> bool:
        folded = self.legal_text_service._fold_text(
            f"{item.get('title', '')} {item.get('article') or ''} {item.get('content', '')}"
        )
        if "thue thu nhap ca nhan" not in folded:
            return False
        article = item.get("article")
        if article == "Điều 8" and "tien luong" not in folded:
            return False
        if article == "Điều 21" and ("tien luong" not in folded or "khong cu tru" not in folded):
            return False
        return article in {"Điều 2", "Điều 3", "Điều 8", "Điều 10", "Điều 21"} and any(
            term in folded
            for term in ("nguoi nop thue", "thu nhap chiu thue", "thu nhap tinh thue", "giam tru gia canh", "tien luong", "khong cu tru")
        )

    # ------------------------------------------------------------------ #
    #  Prize threshold coverage
    # ------------------------------------------------------------------ #

    def _ensure_prize_threshold_coverage(self, selected: list[dict], candidates: list[dict], limit: int) -> list[dict]:
        required: list[dict] = []
        required_ids: set[str] = set()
        for threshold in ("20 trieu", "10 trieu"):
            candidate = next((item for item in candidates if self._is_prize_threshold_candidate(item, threshold)), None)
            if candidate and candidate["id"] not in required_ids:
                required.append(candidate)
                required_ids.add(candidate["id"])

        if not required:
            return selected

        remaining = [item for item in selected if item["id"] not in required_ids]
        return (required + remaining)[:limit]

    def _is_prize_threshold_candidate(self, item: dict, threshold: str) -> bool:
        folded_content = self.legal_text_service._fold_text(item["content"])
        return threshold in folded_content and "trung thuong" in folded_content and "10%" in folded_content

    # ------------------------------------------------------------------ #
    #  Citation formatting
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
