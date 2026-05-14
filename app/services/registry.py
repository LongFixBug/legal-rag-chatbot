from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.config import Settings, get_settings
from app.db.interfaces import MetadataStore, VectorStore
from app.db.postgres import LocalMetadataStore, PostgresMetadataStore
from app.db.qdrant import LocalVectorStore, QdrantVectorStore
from app.services.citation import CitationService
from app.services.document import DocumentService
from app.services.embedding import build_embedding_service
from app.services.legal import LegalTextService
from app.services.llm import build_llm_service
from app.services.parser import DocumentParserService
from app.services.rag import RagService


@dataclass(slots=True)
class AppServices:
    settings: Settings
    metadata_store: MetadataStore
    vector_store: VectorStore
    documents: DocumentService
    rag: RagService

    async def close(self) -> None:
        await self.vector_store.close()
        await self.metadata_store.close()


async def build_services() -> AppServices:
    settings = get_settings()
    metadata_store: MetadataStore = (
        PostgresMetadataStore(settings.database_url) if settings.use_postgres else LocalMetadataStore(settings.storage_dir)
    )
    vector_store: VectorStore = (
        QdrantVectorStore(settings.qdrant_url, settings.qdrant_collection, settings.embedding_dimension)
        if settings.use_qdrant
        else LocalVectorStore(settings.storage_dir)
    )
    await metadata_store.init()
    await vector_store.init()

    citation_service = CitationService()
    legal_text_service = LegalTextService()
    parser_service = DocumentParserService()
    embedding_service = build_embedding_service(settings)
    llm_service = build_llm_service(settings)
    document_service = DocumentService(
        metadata_store=metadata_store,
        vector_store=vector_store,
        embedding_service=embedding_service,
        legal_text_service=legal_text_service,
        citation_service=citation_service,
        parser_service=parser_service,
    )
    rag_service = RagService(
        settings=settings,
        metadata_store=metadata_store,
        vector_store=vector_store,
        embedding_service=embedding_service,
        llm_service=llm_service,
        citation_service=citation_service,
        legal_text_service=legal_text_service,
    )
    return AppServices(
        settings=settings,
        metadata_store=metadata_store,
        vector_store=vector_store,
        documents=document_service,
        rag=rag_service,
    )



def get_services(request: Request) -> AppServices:
    return request.app.state.services
