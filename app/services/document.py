from __future__ import annotations

import uuid
from hashlib import sha256
from pathlib import Path

from app.config import Settings
from app.db.interfaces import MetadataStore, VectorStore
from app.db.models import ChunkRecord, DocumentRecord
from app.schemas.document import DocumentIngestRequest
from app.services.citation import CitationService
from app.services.embedding import EmbeddingService
from app.services.legal import LegalTextService
from app.services.parser import DocumentParserService


class DocumentService:
    def __init__(
        self,
        metadata_store: MetadataStore,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        legal_text_service: LegalTextService,
        citation_service: CitationService,
        parser_service: DocumentParserService,
        settings: Settings,
    ):
        self.metadata_store = metadata_store
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.legal_text_service = legal_text_service
        self.citation_service = citation_service
        self.parser_service = parser_service
        self.settings = settings

    async def ingest_document(self, request: DocumentIngestRequest) -> tuple[DocumentRecord, int]:
        content_hash = self._content_sha256(request.content)
        identity_key = f"sha256:{content_hash}"
        existing = await self._find_existing_document(identity_key)
        if existing is not None:
            chunks = await self.metadata_store.list_chunks(existing.id)
            return existing, len(chunks)

        title = self.legal_text_service.guess_title(request.content, request.title)
        document = DocumentRecord(
            id=str(uuid.uuid4()),
            title=title,
            source=request.source,
            doc_type=request.doc_type,
            summary=self.legal_text_service.summarize(request.content),
            metadata={
                "manual_title": request.title,
                "content_sha256": content_hash,
                "identity_key": identity_key,
                "parser_version": self.settings.parser_version,
                "chunking_version": self.settings.chunking_version,
                "embedding_dimension": self.settings.embedding_dimension,
                "qdrant_collection": self.settings.qdrant_collection,
            },
        )
        await self.metadata_store.upsert_document(document)
        chunks = await self._build_chunks(document.id, request.content)
        await self.metadata_store.replace_document_chunks(document.id, chunks)
        await self.vector_store.delete_by_document(document.id)
        for chunk in chunks:
            vector = await self.embedding_service.embed(chunk.content)
            await self.vector_store.upsert(
                chunk.id,
                vector,
                {
                    "document_id": document.id,
                    "title": document.title,
                    "article": chunk.article,
                    "clause": chunk.clause,
                    "content": chunk.content,
                    "citations": chunk.citations,
                },
            )
        return document, len(chunks)

    async def ingest_uploaded_file(self, title: str, filename: str, content: bytes) -> tuple[DocumentRecord, int]:
        parsed_text = self.parser_service.parse_uploaded_file(filename, content)
        return await self.ingest_document(
            DocumentIngestRequest(title=title, content=parsed_text, source=filename, doc_type="uploaded_file")
        )

    async def ingest_directory(self, directory: Path, include_pattern: str = "*") -> int:
        ingested = 0
        existing_sources = {doc.source for doc in await self.metadata_store.list_documents()}
        for file_path in sorted(directory.glob(include_pattern or "*")):
            if not file_path.is_file() or file_path.suffix.lower() not in {".txt", ".md", ".html", ".htm"}:
                continue
            if file_path.stem.lower() == "readme":
                continue
            if str(file_path) in existing_sources:
                continue
            raw_bytes = file_path.read_bytes()
            parsed_text = self.parser_service.parse_uploaded_file(file_path.name, raw_bytes)
            request = DocumentIngestRequest(
                title=file_path.stem.replace("-", " ").title(),
                content=parsed_text,
                source=str(file_path),
                doc_type=file_path.suffix.lower().lstrip("."),
            )
            await self.ingest_document(request)
            ingested += 1
        return ingested

    async def reindex_directory(self, directory: Path, include_pattern: str = "*") -> tuple[int, int]:
        deleted = 0
        for document in await self.metadata_store.list_documents():
            if not self._is_directory_source(document.source, directory):
                continue
            await self.delete_document(document.id)
            deleted += 1
        ingested = await self.ingest_directory(directory, include_pattern)
        return deleted, ingested

    async def list_documents(self) -> list[DocumentRecord]:
        return await self.metadata_store.list_documents()

    async def delete_document(self, document_id: str) -> bool:
        document = await self.metadata_store.get_document(document_id)
        if not document:
            return False
        await self.metadata_store.delete_document(document_id)
        await self.vector_store.delete_by_document(document_id)
        return True

    async def _find_existing_document(self, identity_key: str) -> DocumentRecord | None:
        for document in await self.metadata_store.list_documents():
            if document.metadata.get("identity_key") == identity_key:
                return document
        return None

    async def _build_chunks(self, document_id: str, content: str) -> list[ChunkRecord]:
        chunks: list[ChunkRecord] = []
        for raw_chunk in self.legal_text_service.split_legal_text(content):
            chunk_id = str(uuid.uuid4())
            article = self.citation_service.extract_primary_article(raw_chunk)
            clause = self.citation_service.extract_primary_clause(raw_chunk)
            citations = self.citation_service.extract_references(raw_chunk)
            chunks.append(
                ChunkRecord(
                    id=chunk_id,
                    document_id=document_id,
                    content=raw_chunk,
                    article=article,
                    clause=clause,
                    citations=citations,
                    metadata={"length": len(raw_chunk)},
                )
            )
        return chunks

    @staticmethod
    def _is_directory_source(source: str, directory: Path) -> bool:
        try:
            source_path = Path(source).resolve()
            directory_path = directory.resolve()
            return source_path.is_relative_to(directory_path)
        except (OSError, RuntimeError, ValueError):
            return False

    @staticmethod
    def _content_sha256(content: str) -> str:
        normalized = "\n".join(line.rstrip() for line in content.strip().splitlines())
        return sha256(normalized.encode("utf-8")).hexdigest()
