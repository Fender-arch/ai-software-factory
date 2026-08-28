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
    groq_api_key: str = ""
    stt_provider: str = "stub"
    stt_model: str = "whisper-1"
    owner_telegram_id: str = ""
    llm_provider: str = "stub"
    llm_model: str = ""
    discovery_engine: str = "auto"
    miniapp_url: str = ""
    console_token: str = ""
    upload_dir: str = "data/uploads"
    max_upload_bytes: int = 20 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
