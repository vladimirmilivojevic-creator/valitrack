from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/valitrack"
    secret_key: str = "dev-only-secret-change-me"
    demo_mode: bool = False
    demo_reset_token: str = ""
    cookie_secure: bool = False

    session_minutes: int = 30
    lockout_threshold: int = 5
    lockout_minutes: int = 15
    max_evidence_bytes: int = 2 * 1024 * 1024
    static_dir: str = ""
    fast_hashing: bool = False  # cheaper password hashing, only for the automated tests

    @property
    def sqlalchemy_url(self) -> str:
        """Accept plain postgresql:// strings (Neon, Render) and select the psycopg 3 driver."""
        url = self.database_url
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    @property
    def effective_lockout_minutes(self) -> int:
        # A public demo must not stay locked for long when a visitor mistypes a password.
        return 1 if self.demo_mode else self.lockout_minutes


@lru_cache
def get_settings() -> Settings:
    return Settings()
