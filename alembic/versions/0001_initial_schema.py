"""initial metadata schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-18 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("source", sa.String(length=1000), nullable=False),
        sa.Column("doc_type", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.String(length=2000), nullable=False),
        sa.Column("created_at", sa.String(length=100), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("article", sa.String(length=100), nullable=True),
        sa.Column("clause", sa.String(length=100), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_article", "chunks", ["article"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.String(length=100), nullable=False),
        sa.Column("updated_at", sa.String(length=100), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.String(length=100), nullable=False, server_default="legacy"),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(length=100), nullable=False),
    )
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_conversation_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_table("conversations")
    op.drop_index("ix_chunks_article", table_name="chunks")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("documents")
