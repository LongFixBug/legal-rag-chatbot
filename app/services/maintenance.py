from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.db.interfaces import MetadataStore
from app.services.document import DocumentService


@dataclass(frozen=True)
class RetentionPurgeResult:
    documents_deleted: int
    conversations_deleted: int


class MaintenanceService:
    def __init__(self, settings: Settings, metadata_store: MetadataStore, document_service: DocumentService):
        self.settings = settings
        self.metadata_store = metadata_store
        self.document_service = document_service

    async def purge_expired_data(self) -> RetentionPurgeResult:
        documents_deleted = await self._purge_expired_uploaded_documents()
        conversations_deleted = await self._purge_expired_conversations()
        return RetentionPurgeResult(
            documents_deleted=documents_deleted,
            conversations_deleted=conversations_deleted,
        )

    async def _purge_expired_uploaded_documents(self) -> int:
        cutoff = self._cutoff(self.settings.uploaded_document_retention_days)
        if cutoff is None:
            return 0

        deleted = 0
        for document in await self.metadata_store.list_documents():
            if document.doc_type != "uploaded_file":
                continue
            created_at = self._parse_iso_datetime(document.created_at)
            if created_at is None or created_at >= cutoff:
                continue
            if await self.document_service.delete_document(document.id):
                deleted += 1
        return deleted

    async def _purge_expired_conversations(self) -> int:
        cutoff = self._cutoff(self.settings.chat_history_retention_days)
        if cutoff is None:
            return 0

        deleted = 0
        for conversation in await self.metadata_store.list_conversations():
            updated_at = self._parse_iso_datetime(conversation.updated_at)
            if updated_at is None or updated_at >= cutoff:
                continue
            await self.metadata_store.delete_conversation(conversation.id)
            deleted += 1
        return deleted

    @staticmethod
    def _cutoff(retention_days: int) -> datetime | None:
        if retention_days <= 0:
            return None
        return datetime.now(timezone.utc) - timedelta(days=retention_days)

    @staticmethod
    def _parse_iso_datetime(value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
