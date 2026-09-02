"""
Application configuration.

All values are read from environment variables (or a `.env` file placed
next to this module). See `.env.example` for the full list.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- PostgreSQL ----
    # e.g. postgresql+psycopg2://syllabusquest:secret@localhost:5432/syllabusquest
    DATABASE_URL: str = "postgresql+psycopg2://syllabusquest:syllabusquest@localhost:5432/syllabusquest"

    # ---- Auth / JWT ----
    SECRET_KEY: str = "change-this-to-a-long-random-string"  # openssl rand -hex 32
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12  # 12 hours

    # ---- Password reset ----
    RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # ---- Bootstrap admin (created by seed script if no admin exists) ----
    DEFAULT_ADMIN_USERID: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"  # CHANGE THIS after first login

    # ---- CORS ----
    CORS_ORIGINS: str = "*"  # comma-separated list in production, e.g. "https://yourapp.com"

    # ---- Optional SMTP (for actually emailing password-reset links) ----
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None
    # Base URL of the frontend, used to build the reset link, e.g. https://app.example.com
    FRONTEND_RESET_URL: str = "http://localhost:8000/reset-password.html"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
