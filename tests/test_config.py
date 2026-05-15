import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_require_llm_model_when_llm_base_url_is_configured():
    with pytest.raises(ValidationError):
        Settings(llm_base_url="http://127.0.0.1:8080")


def test_settings_require_embedding_model_when_embedding_base_url_is_configured():
    with pytest.raises(ValidationError):
        Settings(embedding_base_url="http://127.0.0.1:8081")


def test_settings_allow_shared_openai_style_configuration_when_both_models_exist():
    settings = Settings(
        openai_base_url="https://example.test/v1",
        openai_chat_model="chat-model",
        openai_embedding_model="embed-model",
    )
    assert settings.resolved_llm_base_url == "https://example.test/v1"
    assert settings.resolved_embedding_base_url == "https://example.test/v1"

