from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CodeTeam Agent API"
    environment: str = "development"
    database_url: str = "sqlite:///./codeteam.db"
    repository_root: Path = Path("./data/repositories")
    llm_provider: str = "fake"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    embedding_provider: str = "hash"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: Literal[1536] = 1536
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    task_dispatch_mode: str = "local"
    agent_max_retrieval_attempts: int = 2
    agent_max_revision_attempts: int = 2
    sandbox_root: Path = Path("./data/sandboxes")
    sandbox_timeout_seconds: int = 120
    sandbox_allowed_commands: str = "pytest,ruff"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
