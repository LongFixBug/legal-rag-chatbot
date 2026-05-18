from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RAG Legal Assistant"
    app_version: str = "0.2.0"
    api_prefix: str = "/api"
    storage_dir: Path = Field(default=Path(".storage"))
    data_dir: Path = Field(default=Path("data"))
    preload_sample_data: bool = True
    preload_include_pattern: str = "nghia-vu-quan-su-curated-*.txt"
    embedding_dimension: int = Field(default=1024, gt=0)
    top_k: int = Field(default=4, ge=1)
    max_history_messages: int = Field(default=6, ge=0)
    lexical_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    article_reference_boost: float = Field(default=0.75, ge=0.0)
    title_match_boost: float = Field(default=0.2, ge=0.0)
    min_retrieval_confidence: float = Field(default=0.2, ge=0.0, le=1.0)
    admin_token: str = ""
    rate_limit_enabled: bool = True
    chat_rate_limit_per_minute: int = Field(default=30, ge=0)
    document_mutation_rate_limit_per_minute: int = Field(default=12, ge=0)
    max_upload_bytes: int = Field(default=5_242_880, gt=0)
    allowed_upload_extensions: str = ".txt,.md,.html,.htm,.pdf"
    allowed_upload_mime_types: str = "text/plain,text/markdown,text/html,application/pdf"
    parser_version: str = "parser.v1"
    chunking_version: str = "legal-article-chunker.v1"
    uploaded_document_retention_days: int = Field(default=0, ge=0)
    chat_history_retention_days: int = Field(default=0, ge=0)

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
    llm_timeout_seconds: float = Field(default=60.0, gt=0.0)
    llm_max_retries: int = Field(default=1, ge=0)
    embedding_timeout_seconds: float = Field(default=30.0, gt=0.0)
    embedding_max_retries: int = Field(default=1, ge=0)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_runtime_config(self) -> "Settings":
        remote_pairs = (
            ("LLM", self.resolved_llm_base_url, self.resolved_llm_model),
            ("Embedding", self.resolved_embedding_base_url, self.resolved_embedding_model),
        )
        for name, base_url, model in remote_pairs:
            if bool(base_url) ^ bool(model):
                raise ValueError(f"{name} remote config requires both base URL and model")
        if self.database_url and not self.database_url.startswith("postgresql+"):
            raise ValueError("DATABASE_URL must start with 'postgresql+' when configured")
        if self.qdrant_url and not self.qdrant_url.startswith("http"):
            raise ValueError("QDRANT_URL must start with 'http' when configured")
        return self

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
