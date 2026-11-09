from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = SERVICE_DIR.parent.parent
SRC_DIR = SERVICE_DIR / "src"
TESTS_DIR = SERVICE_DIR / "tests"
SCRIPTS_DIR = SERVICE_DIR / "scripts"


class LLMConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=SERVICE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model: str = ""
    url: str = "http://127.0.0.1:8080/v1"
    api_key: str = "no-key"
    timeout: int = 60
    max_tokens: int = 2000
    temperature: float = 0.2
    context_window: int = 8000


class QdrantConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QDRANT_",
        env_file=SERVICE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    url: str = "http://127.0.0.1:6333"
    collection_name: str = "default"
