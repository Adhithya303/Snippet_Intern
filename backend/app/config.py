from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")
    # SQLite is a documented preview fallback; .env selects PostgreSQL when configured.
    database_url: str = "sqlite:///./preview.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # External LLM Configuration (Google Gemini Developer API - Free tier)
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.1-flash-lite"
    llm_timeout_seconds: float = 15.0
