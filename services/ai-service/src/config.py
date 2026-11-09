from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = SERVICE_DIR.parent.parent
SRC_DIR = SERVICE_DIR / "src"
TESTS_DIR = SERVICE_DIR / "tests"
SCRIPTS_DIR = SERVICE_DIR / "scripts"


class BaseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=SERVICE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class LLMConfig(BaseConfig):
    model_config = SettingsConfigDict(
        env_prefix="LLM_",
    )

    url: str = Field(
        default="http://127.0.0.1:8080/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL", "LLM_URL"),
    )
    model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_MODEL", "OPENAI_MODEL", "GEN_MODEL"),
    )
    api_key: str = Field(
        default="no-key",
        validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY"),
    )
    max_tokens: int = Field(
        default=2000,
        validation_alias=AliasChoices("MAX_TOKENS", "LLM_MAX_TOKENS"),
    )
    temperature: float = Field(
        default=0.2,
        validation_alias=AliasChoices("TEMPERATURE", "LLM_TEMPERATURE"),
    )
    timeout: int = 60
    context_window: int = 10000


class EmbeddingConfig(BaseConfig):
    model_config = SettingsConfigDict(
        env_prefix="EMB_",
    )

    url: str = Field(
        default="http://127.0.0.1:8080/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL", "EMB_URL"),
    )
    model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMB_MODEL"),
    )


class RerankerConfig(BaseConfig):
    url: str = Field(
        default="http://127.0.0.1:8080/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL", "RRK_URL"),
    )
    model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RERANKER_MODEL", "RRK_MODEL"),
    )
    top_n: int = Field(
        default=5,
        validation_alias=AliasChoices("RERANKER_TOP_N", "RRK_TOP_N"),
    )


class RAGConfig(BaseConfig):
    top_k: int = Field(
        default=15,
        validation_alias=AliasChoices("TOP_K", "RAG_TOP_K"),
    )
    chunker: str = Field(
        default="common",
        validation_alias=AliasChoices("CHUNKER", "RAG_CHUNKER"),
    )


class QdrantConfig(BaseConfig):
    model_config = SettingsConfigDict(
        env_prefix="QDRANT_",
    )

    url: str = "http://127.0.0.1:6333"
    collection_name: str = "default"


class Settings(BaseConfig):
    max_workers: int = Field(default=5, validation_alias=AliasChoices("MAX_WORKERS"))
    mock_mode: bool = Field(default=False, validation_alias=AliasChoices("MOCK_MODE"))

    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)

    @property
    def is_mock(self) -> bool:
        return (
            self.mock_mode
            or self.llm.model is None
            or self.embedding.model is None
            or self.reranker.model is None
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
