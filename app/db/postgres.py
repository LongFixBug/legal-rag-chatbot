from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import JSON, String, delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.interfaces import MetadataStore
from app.db.models import ChatMessageRecord, ChunkRecord, ConversationRecord, DocumentRecord


class LocalMetadataStore(MetadataStore):
    def __init__(self, storage_dir: Path):
        self._path = storage_dir / "metadata.json"
        if not self._path.exists():
            self._write({"documents": [], "chunks": [], "conversations": [], "chat_history": []})
        else:
            self._migrate_if_needed()

    async def init(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def _read(self) -> dict:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write(self, payload: dict) -> None:
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _migrate_if_needed(self) -> None:
        payload = self._read()
        changed = False
        if "conversations" not in payload:
            payload["conversations"] = []
            changed = True
        for message in payload.get("chat_history", []):
            if "conversation_id" not in message:
                message["conversation_id"] = "legacy"
                changed = True
        if any(message.get("conversation_id") == "legacy" for message in payload.get("chat_history", [])):
            if not any(conversation.get("id") == "legacy" for conversation in payload["conversations"]):
                payload["conversations"].append(
                    ConversationRecord(id="legacy", title="Legacy conversation", metadata={"migrated": True}).to_dict()
                )
                changed = True
        if changed:
            self._write(payload)

    async def list_documents(self) -> list[DocumentRecord]:
        payload = self._read()
        return [DocumentRecord(**item) for item in payload["documents"]]

    async def get_document(self, document_id: str) -> DocumentRecord | None:
        for document in await self.list_documents():
            if document.id == document_id:
                return document
        return None

    async def upsert_document(self, record: DocumentRecord) -> None:
        payload = self._read()
        docs = [doc for doc in payload["documents"] if doc["id"] != record.id]
        docs.append(record.to_dict())
        payload["documents"] = docs
        self._write(payload)

    async def delete_document(self, document_id: str) -> None:
        payload = self._read()
        payload["documents"] = [doc for doc in payload["documents"] if doc["id"] != document_id]
        payload["chunks"] = [chunk for chunk in payload["chunks"] if chunk["document_id"] != document_id]
        self._write(payload)

    async def list_chunks(self, document_id: str | None = None) -> list[ChunkRecord]:
        payload = self._read()
        chunks = payload["chunks"]
        if document_id:
            chunks = [chunk for chunk in chunks if chunk["document_id"] == document_id]
        return [ChunkRecord(**item) for item in chunks]

    async def replace_document_chunks(self, document_id: str, chunks: list[ChunkRecord]) -> None:
        payload = self._read()
        rest = [chunk for chunk in payload["chunks"] if chunk["document_id"] != document_id]
        payload["chunks"] = rest + [chunk.to_dict() for chunk in chunks]
        self._write(payload)

    async def create_conversation(self, record: ConversationRecord) -> None:
        payload = self._read()
        conversations = [item for item in payload["conversations"] if item["id"] != record.id]
        conversations.append(record.to_dict())
        payload["conversations"] = conversations
        self._write(payload)

    async def get_conversation(self, conversation_id: str) -> ConversationRecord | None:
        payload = self._read()
        for item in payload["conversations"]:
            if item["id"] == conversation_id:
                return ConversationRecord(**item)
        return None

    async def list_conversations(self, limit: int | None = None) -> list[ConversationRecord]:
        payload = self._read()
        conversations = [ConversationRecord(**item) for item in payload["conversations"]]
        conversations.sort(key=lambda item: item.updated_at, reverse=True)
        return conversations[:limit] if limit is not None else conversations

    async def delete_conversation(self, conversation_id: str) -> None:
        payload = self._read()
        payload["conversations"] = [item for item in payload["conversations"] if item["id"] != conversation_id]
        payload["chat_history"] = [item for item in payload["chat_history"] if item["conversation_id"] != conversation_id]
        self._write(payload)

    async def append_chat(self, message: ChatMessageRecord) -> None:
        payload = self._read()
        payload["chat_history"].append(message.to_dict())
        for conversation in payload["conversations"]:
            if conversation["id"] == message.conversation_id:
                conversation["updated_at"] = message.created_at
        self._write(payload)

    async def list_chat_history(self, conversation_id: str, limit: int | None = None) -> list[ChatMessageRecord]:
        payload = self._read()
        history = [
            ChatMessageRecord(**item)
            for item in payload["chat_history"]
            if item["conversation_id"] == conversation_id
        ]
        if limit is not None:
            history = history[-limit:]
        return history


class Base(DeclarativeBase):
    pass


class DocumentORM(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(1000), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[str] = mapped_column(String(100), nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class ChunkORM(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    article: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    clause: Mapped[str | None] = mapped_column(String(100), nullable=True)
    citations_json: Mapped[list] = mapped_column("citations", JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class ConversationORM(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[str] = mapped_column(String(100), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(100), nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class ChatMessageORM(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False, default="legacy")
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String(100), nullable=False)


class PostgresMetadataStore(MetadataStore):
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, future=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS conversation_id VARCHAR(100) DEFAULT 'legacy'"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_messages_conversation_id ON chat_messages (conversation_id)"))
        async with self.session_factory() as session:
            legacy_exists = await session.get(ConversationORM, "legacy")
            if legacy_exists is None:
                session.add(ConversationORM(id="legacy", title="Legacy conversation", created_at="1970-01-01T00:00:00+00:00", updated_at="1970-01-01T00:00:00+00:00", metadata_json={"migrated": True}))
                await session.commit()

    async def close(self) -> None:
        await self.engine.dispose()

    async def list_documents(self) -> list[DocumentRecord]:
        async with self.session_factory() as session:
            rows = (await session.execute(select(DocumentORM).order_by(DocumentORM.created_at.asc()))).scalars().all()
            return [self._document_from_row(row) for row in rows]

    async def get_document(self, document_id: str) -> DocumentRecord | None:
        async with self.session_factory() as session:
            row = await session.get(DocumentORM, document_id)
            return self._document_from_row(row) if row else None

    async def upsert_document(self, record: DocumentRecord) -> None:
        async with self.session_factory() as session:
            row = await session.get(DocumentORM, record.id)
            if row is None:
                row = DocumentORM(id=record.id)
                session.add(row)
            row.title = record.title
            row.source = record.source
            row.doc_type = record.doc_type
            row.summary = record.summary
            row.created_at = record.created_at
            row.metadata_json = record.metadata
            await session.commit()

    async def delete_document(self, document_id: str) -> None:
        async with self.session_factory() as session:
            await session.execute(delete(ChunkORM).where(ChunkORM.document_id == document_id))
            await session.execute(delete(DocumentORM).where(DocumentORM.id == document_id))
            await session.commit()

    async def list_chunks(self, document_id: str | None = None) -> list[ChunkRecord]:
        async with self.session_factory() as session:
            stmt = select(ChunkORM)
            if document_id:
                stmt = stmt.where(ChunkORM.document_id == document_id)
            rows = (await session.execute(stmt.order_by(ChunkORM.id.asc()))).scalars().all()
            return [self._chunk_from_row(row) for row in rows]

    async def replace_document_chunks(self, document_id: str, chunks: list[ChunkRecord]) -> None:
        async with self.session_factory() as session:
            await session.execute(delete(ChunkORM).where(ChunkORM.document_id == document_id))
            for chunk in chunks:
                session.add(
                    ChunkORM(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        content=chunk.content,
                        article=chunk.article,
                        clause=chunk.clause,
                        citations_json=chunk.citations,
                        metadata_json=chunk.metadata,
                    )
                )
            await session.commit()

    async def create_conversation(self, record: ConversationRecord) -> None:
        async with self.session_factory() as session:
            row = await session.get(ConversationORM, record.id)
            if row is None:
                row = ConversationORM(id=record.id)
                session.add(row)
            row.title = record.title
            row.created_at = record.created_at
            row.updated_at = record.updated_at
            row.metadata_json = record.metadata
            await session.commit()

    async def get_conversation(self, conversation_id: str) -> ConversationRecord | None:
        async with self.session_factory() as session:
            row = await session.get(ConversationORM, conversation_id)
            return self._conversation_from_row(row) if row else None

    async def list_conversations(self, limit: int | None = None) -> list[ConversationRecord]:
        async with self.session_factory() as session:
            stmt = select(ConversationORM).order_by(ConversationORM.updated_at.desc())
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            return [self._conversation_from_row(row) for row in rows]

    async def delete_conversation(self, conversation_id: str) -> None:
        async with self.session_factory() as session:
            await session.execute(delete(ChatMessageORM).where(ChatMessageORM.conversation_id == conversation_id))
            await session.execute(delete(ConversationORM).where(ConversationORM.id == conversation_id))
            await session.commit()

    async def append_chat(self, message: ChatMessageRecord) -> None:
        async with self.session_factory() as session:
            session.add(
                ChatMessageORM(
                    conversation_id=message.conversation_id,
                    role=message.role,
                    content=message.content,
                    created_at=message.created_at,
                )
            )
            conversation = await session.get(ConversationORM, message.conversation_id)
            if conversation is not None:
                conversation.updated_at = message.created_at
            await session.commit()

    async def list_chat_history(self, conversation_id: str, limit: int | None = None) -> list[ChatMessageRecord]:
        async with self.session_factory() as session:
            stmt = select(ChatMessageORM).where(ChatMessageORM.conversation_id == conversation_id).order_by(ChatMessageORM.id.desc())
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            ordered = list(reversed(rows))
            return [
                ChatMessageRecord(
                    conversation_id=row.conversation_id,
                    role=row.role,
                    content=row.content,
                    created_at=row.created_at,
                )
                for row in ordered
            ]

    @staticmethod
    def _document_from_row(row: DocumentORM) -> DocumentRecord:
        return DocumentRecord(
            id=row.id,
            title=row.title,
            source=row.source,
            doc_type=row.doc_type,
            summary=row.summary,
            created_at=row.created_at,
            metadata=row.metadata_json or {},
        )

    @staticmethod
    def _chunk_from_row(row: ChunkORM) -> ChunkRecord:
        return ChunkRecord(
            id=row.id,
            document_id=row.document_id,
            content=row.content,
            article=row.article,
            clause=row.clause,
            citations=row.citations_json or [],
            metadata=row.metadata_json or {},
        )

    @staticmethod
    def _conversation_from_row(row: ConversationORM) -> ConversationRecord:
        return ConversationRecord(
            id=row.id,
            title=row.title,
            created_at=row.created_at,
            updated_at=row.updated_at,
            metadata=row.metadata_json or {},
        )
