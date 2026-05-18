from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config


def test_alembic_initial_migration_creates_metadata_tables(tmp_path: Path):
    database_path = tmp_path / "migration-test.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")

    engine = sa.create_engine(f"sqlite:///{database_path}")
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())

    assert {"documents", "chunks", "conversations", "chat_messages"}.issubset(tables)
    assert "conversation_id" in {column["name"] for column in inspector.get_columns("chat_messages")}
    assert "article" in {column["name"] for column in inspector.get_columns("chunks")}
