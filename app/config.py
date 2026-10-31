from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_tailor_model: str = "gemini-3.5-flash-lite"
    database_url: str = "sqlite:///./storage/jobpilot.db"
    timezone: str = "Europe/Berlin"
    daily_run_hour: int = 7
    enable_scheduler: bool = False
    minimum_match_score: int = 70
    max_llm_calls_per_run: int = 30
    max_jobs_per_run: int = 100
    max_new_jobs_per_run: int = 500
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
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    enable_arbeitnow: bool = True
    enable_bundesagentur: bool = True
    bundesagentur_api_key: str = "jobboerse-jobsuche"
    enable_adzuna: bool = False
    enable_eures: bool = False
    enable_smartrecruiters: bool = True
    enable_personio: bool = True
    enable_recruitee: bool = True
    enable_workable: bool = True
    enable_teamtailor: bool = True
    recruitee_token: str = ""
    workable_token: str = ""
    teamtailor_token: str = ""
    enable_jobicy: bool = True
    enable_himalayas: bool = True
    enable_email_alerts: bool = False
    auto_discover_company_boards: bool = True
    job_search_country: str = "DE"
    source_timeout_seconds: int = 20
    max_source_pages: int = 3
    discovery_keywords: str = (
        "Junior Project Manager,Projektmanager,Junior Projektmanager,Projektkoordinator,"
        "Project Coordinator,PMO,Projektmanagement Office,Projektassistenz,Program Coordinator,"
        "Junior Product Manager,Associate Product Manager,Produktmanager,Product Owner,"
        "Product Specialist,Business Analyst,Business Operations Analyst,Business Process Analyst,"
        "Implementation Specialist,Operations Analyst,Process Engineer,Prozessingenieur,"
        "Prozessoptimierung,Continuous Improvement,Innovation Manager,Technology Project Manager,"
        "Digital Transformation,Change Management"
    )
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
