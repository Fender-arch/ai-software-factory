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
    # Printed on the client TZ (not secrets; HITL still uses owner_telegram_id).
    studio_name: str = ""
    owner_contact_name: str = ""
    owner_contact_email: str = ""
    owner_contact_phone: str = ""
    owner_contact_telegram: str = ""
    llm_provider: str = "stub"
    llm_model: str = ""
    discovery_engine: str = "auto"
    miniapp_url: str = ""
    console_token: str = ""
    upload_dir: str = "data/uploads"
    max_upload_bytes: int = 20 * 1024 * 1024
    # Owner delivery-cost heuristic when a draft TZ is ready (Telegram DM).
    # Env: ASF_ESTIMATE_HOURLY_RATE, ASF_ESTIMATE_CURRENCY
    asf_estimate_hourly_rate: float = 3000
    asf_estimate_currency: str = "RUB"
    # Optional public JSON of market bands for the client estimate (DEC-012).
    # Host must be listed in ASF_MARKET_RATES_ALLOWLIST (comma-separated). HTTPS only.
    asf_market_rates_url: str = ""
    asf_market_rates_allowlist: str = ""
    # DEC-013: Intervention Queue + Cursor executor (optional).
    asf_intervention_key: str = ""
    asf_intervention_ttl_hours: int = 72
    cursor_api_key: str = ""
    cursor_cloud_api_url: str = "https://api.cursor.com"
    cursor_agent_repo: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
