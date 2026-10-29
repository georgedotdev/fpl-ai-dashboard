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
    # Also allow origins matching this pattern, e.g. Cloudflare Pages preview links:
    # ^https://([a-z0-9-]+\.)?fpl-ai-dashboard\.pages\.dev$
    cors_origin_regex: str | None = None

    # Requests per visitor per minute to the endpoints that run the optimizer
    # (recommendations, hand-entered squads, best XI). Protects a small free server.
    rate_limit_per_minute: int = 30

    # Which prediction brain feeds the optimizer and dashboard (see app/prediction).
    predictor: str = "baseline-form-fixtures"
    # Planning horizon in gameweeks (spec open question 7, decided in D-010).
    default_horizon: int = 5
    max_horizon: int = 8

    # Explanation layer (D-014): a local language model served by Ollama, if one is set;
    # otherwise explanations come from the template writer. No API keys either way.
    local_model: str | None = None  # an Ollama model name, e.g. one you've pulled with `ollama pull`
    ollama_url: str = "http://localhost:11434"
    local_model_timeout_s: float = 30.0

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
