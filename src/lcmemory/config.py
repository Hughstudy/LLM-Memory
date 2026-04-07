"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the memory system."""

    model_config = SettingsConfigDict(
        env_prefix="LCM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/lcmemory"

    # Compaction
    compaction_threshold: int = 15
    compaction_trigger_mode: str = "oldest_first"  # oldest_first | newest_first

    # LLM
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4096

    # Retrieval
    default_search_limit: int = 20
    default_expand_token_cap: int = 12000
    default_expand_max_depth: int = 3
    default_query_ttl_seconds: int = 300
    default_query_max_expand_tokens: int = 16000

    # Token counting
    token_counter_encoding: str = "cl100k_base"


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the global Settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset the settings singleton (for testing)."""
    global _settings
    _settings = None
