from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    asf_env: str = "local"
    asf_debug: bool = True
    database_url: str = "postgresql+psycopg://asf:asf@localhost:5432/asf"
    telegram_bot_token: str = ""
    openai_api_key: str = ""
    stt_provider: str = "stub"
    stt_model: str = "whisper-1"
    owner_telegram_id: str = ""
    llm_provider: str = "stub"


@lru_cache
def get_settings() -> Settings:
    return Settings()
