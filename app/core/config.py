"""Application configuration and environment settings."""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    APP_NAME: str = "Student Resume Analyzer"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    VERSION: str = "0.1.0"

    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    MAX_UPLOAD_SIZE_MB: int = 5
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx"]
    MAX_PAGE_COUNT: int = 10
    MIN_EXTRACTED_CHARS_WARNING: int = 100
    MIN_PAGE_CHARS_SCANNED_CHECK: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
