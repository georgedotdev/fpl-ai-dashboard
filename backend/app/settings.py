"""Runtime configuration, read from environment variables (prefix FPLAI_) or backend/.env."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FPLAI_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://fpl:fpl@localhost:5432/fpl"
    season: str = "2026_27"

    fpl_base_url: str = "https://fantasy.premierleague.com/api/"
    fpl_timeout_s: float = 15.0
    # Minimum gap between two requests to FPL. The API is unofficial; be polite.
    fpl_min_interval_s: float = 0.2

    cors_origins: list[str] = ["http://localhost:5173"]

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, url: str) -> str:
        # Hosted providers (Neon included) hand out postgres:// or postgresql:// URLs;
        # SQLAlchemy needs the driver named explicitly.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
