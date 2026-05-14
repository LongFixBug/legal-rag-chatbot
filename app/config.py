from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RAG Legal Assistant"
    app_version: str = "0.2.0"
    api_prefix: str = "/api"
    storage_dir: Path = Field(default=Path(".storage"))
    data_dir: Path = Field(default=Path("data"))
    preload_sample_data: bool = True
    embedding_dimension: int = 1024
    top_k: int = 4
    max_history_messages: int = 6
    lexical_weight: float = 0.35
    article_reference_boost: float = 0.75
    title_match_boost: float = 0.2

    database_url: str = ""
    qdrant_url: str = ""
    qdrant_collection: str = "legal_chunks_qwen3"

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""

    openai_base_url: str = ""
    openai_api_key: str = ""
    openai_chat_model: str = ""
    openai_embedding_model: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def resolved_llm_base_url(self) -> str:
        return self.llm_base_url or self.openai_base_url

    @property
    def resolved_llm_api_key(self) -> str:
        return self.llm_api_key or self.openai_api_key

    @property
    def resolved_llm_model(self) -> str:
        return self.llm_model or self.openai_chat_model

    @property
    def resolved_embedding_base_url(self) -> str:
        return self.embedding_base_url or self.openai_base_url

    @property
    def resolved_embedding_api_key(self) -> str:
        return self.embedding_api_key or self.openai_api_key

    @property
    def resolved_embedding_model(self) -> str:
        return self.embedding_model or self.openai_embedding_model

    @property
    def use_postgres(self) -> bool:
        return self.database_url.startswith("postgresql+")

    @property
    def use_qdrant(self) -> bool:
        return self.qdrant_url.startswith("http")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
