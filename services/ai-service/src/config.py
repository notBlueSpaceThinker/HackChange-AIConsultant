import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = SERVICE_DIR.parent.parent
SRC_DIR = SERVICE_DIR / "src"
TESTS_DIR = SERVICE_DIR / "tests"
SCRIPTS_DIR = SERVICE_DIR / "scripts"
DATA_DIR = os.getenv("DATA_DIR", default=PROJECT_DIR / "data")


def _in_docker() -> bool:
    return Path("/.dockerenv").exists() or os.getenv("RUNNING_IN_DOCKER", "").lower() in {
        "1",
        "true",
        "yes",
    }


def _resolve_docker_host_url(url: str) -> str:
    """Map localhost/127.0.0.1 URLs to host.docker.internal inside Docker containers."""
    if not _in_docker():
        return url
    parsed = urlsplit(url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return url
    netloc = f"host.docker.internal:{parsed.port}" if parsed.port else "host.docker.internal"
    if parsed.username or parsed.password:
        auth = parsed.username or ""
        if parsed.password:
            auth = f"{auth}:{parsed.password}"
        netloc = f"{auth}@{netloc}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


class BaseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=SERVICE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )


class _EndpointConfig(BaseConfig):
    """Shared base for model server endpoints with Docker localhost resolution."""

    url: str = "http://127.0.0.1:8080/v1"

    @field_validator("url", mode="after")
    @classmethod
    def _rewrite_localhost_in_docker(cls, value: str) -> str:
        return _resolve_docker_host_url(value)


class LLMConfig(_EndpointConfig):
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
    timeout: float = 240.0
    context_window: int = 10000
    max_retries: int = 5


class EmbeddingConfig(_EndpointConfig):
    model_config = SettingsConfigDict(
        env_prefix="EMB_",
    )

    url: str = Field(
        default="http://127.0.0.1:8080/v1",
        validation_alias=AliasChoices("EMB_URL", "LLM_BASE_URL", "OPENAI_BASE_URL"),
    )
    model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMB_MODEL"),
    )
    api_key: str = Field(
        default="no-key",
        validation_alias=AliasChoices("EMB_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY"),
    )
    embed_dim: int = 1024
    timeout: float = 60.0
    max_retries: int = 5


class RerankerConfig(_EndpointConfig):
    model_config = SettingsConfigDict(
        env_prefix="RRK_",
    )

    url: str = Field(
        default="http://127.0.0.1:8080/v1",
        validation_alias=AliasChoices("RRK_URL", "LLM_BASE_URL", "OPENAI_BASE_URL"),
    )
    model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RERANKER_MODEL", "RRK_MODEL"),
    )
    api_key: str = Field(
        default="no-key",
        validation_alias=AliasChoices("RRK_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY"),
    )
    top_n: int = Field(
        default=5,
        validation_alias=AliasChoices("RERANKER_TOP_N", "RRK_TOP_N"),
    )
    timeout: float = 60.0
    max_retries: int = 5


class RAGConfig(BaseConfig):
    model_config = SettingsConfigDict(
        env_prefix="RAG_",
    )
    top_k: int = Field(
        default=15,
        validation_alias=AliasChoices("TOP_K", "RAG_TOP_K"),
    )
    chunker: str = Field(
        default="common",
        validation_alias=AliasChoices("CHUNKER", "RAG_CHUNKER"),
    )
    max_chunk_chars: int = Field(default=1200)
    chunk_overlap: int = Field(default=150)
    expand_limit_per_doc: int = Field(default=3)
    expand_top_docs: int = Field(default=5)


class QdrantConfig(BaseConfig):
    model_config = SettingsConfigDict(
        env_prefix="QDRANT_",
    )

    url: str = "http://127.0.0.1:6333"
    collection_name: str = "default"


class Settings(BaseConfig):
    max_workers: int = Field(default=5, validation_alias=AliasChoices("MAX_WORKERS"))
    mock_mode: bool = Field(default=False, validation_alias=AliasChoices("MOCK_MODE"))

    cors_origins: list[str] = Field(
        default=["*"],
        validation_alias=AliasChoices("CORS_ORIGINS"),
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)

    @property
    def is_llm_mock(self) -> bool:
        return self.mock_mode or not self.llm.model

    @property
    def is_embedding_mock(self) -> bool:
        return self.mock_mode or not self.embedding.model

    @property
    def is_reranker_mock(self) -> bool:
        return self.mock_mode or not self.reranker.model

    @property
    def is_mock(self) -> bool:
        return self.mock_mode or (
            self.is_llm_mock and self.is_embedding_mock and self.is_reranker_mock
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
