"""
Application configuration.

All values are read from environment variables (or a `.env` file placed
next to this module). See `.env.example` for the full list.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- PostgreSQL ----
    # e.g. postgresql+psycopg://syllabusquest:secret@localhost:5432/syllabusquest
    DATABASE_URL: str = "postgresql+psycopg://syllabusquest:syllabusquest@localhost:5432/syllabusquest"

    # Optional: keep the DB password out of .env entirely. When enabled, the
    # password is looked up from your OS's secure credential store (macOS
    # Keychain, Windows Credential Manager, or Linux Secret Service) instead
    # of being read from DATABASE_URL. Store it once with store_db_password.py,
    # then set USE_KEYCHAIN_FOR_DB_PASSWORD=true below. Local development only
    # — see store_db_password.py for why this isn't used on Render.
    USE_KEYCHAIN_FOR_DB_PASSWORD: bool = False
    DB_USER: str = "syllabusquest"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "syllabusquest"
    KEYCHAIN_SERVICE_NAME: str = "syllabusquest-db"

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

    # ---- Optional email API (for actually emailing password-reset links) ----
    RESEND_API_KEY: str | None = None
    EMAIL_FROM: str | None = None
    FRONTEND_RESET_URL: str = "http://localhost:8000/reset-password.html"
    # Base URL of the frontend, used to build the reset link, e.g. https://app.example.com

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        """The connection string database.py actually uses. Identical to
        DATABASE_URL unless USE_KEYCHAIN_FOR_DB_PASSWORD is on, in which case
        the password is fetched from the OS keychain and substituted in at
        runtime — it's never written to disk in this file or in .env."""
        if not self.USE_KEYCHAIN_FOR_DB_PASSWORD:
            return self.DATABASE_URL

        import keyring
        from urllib.parse import quote_plus

        password = keyring.get_password(self.KEYCHAIN_SERVICE_NAME, self.DB_USER)
        if not password:
            raise RuntimeError(
                f"USE_KEYCHAIN_FOR_DB_PASSWORD is true, but no password is stored "
                f"in the OS keychain for service '{self.KEYCHAIN_SERVICE_NAME}' / "
                f"user '{self.DB_USER}'. Run: python store_db_password.py"
            )
        return (
            f"postgresql+psycopg://{self.DB_USER}:{quote_plus(password)}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()

