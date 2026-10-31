from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    gemini_tailor_model: str = "gemini-2.5-flash"
    database_url: str = "sqlite:///./storage/jobpilot.db"
    timezone: str = "Europe/Berlin"
    daily_run_hour: int = 7
    enable_scheduler: bool = False
    minimum_match_score: int = 70
    max_llm_calls_per_run: int = 30
    max_jobs_per_run: int = 100
    allow_paid_api: bool = False
    local_only: bool = True
    app_password: str = ""
    company_boards_json: str = "{}"
    imap_enabled: bool = False
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
