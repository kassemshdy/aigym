from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables.

    ``database_url`` is the app's runtime connection: a role that is NOT the
    table owner and does NOT have BYPASSRLS, so Postgres actually enforces the
    Row-Level Security policies. ``database_url_migrations`` is a superuser
    (or at least table-owning) connection used only by Alembic and the seed
    script, which must run as the owner to create tables and policies.
    """

    model_config = SettingsConfigDict(env_prefix="AIGYM_", env_file=".env", extra="ignore")

    env: str = "development"

    database_url: str = "postgresql+psycopg://aigym_app:aigym_app@localhost:5432/aigym"
    database_url_migrations: str = "postgresql+psycopg://postgres:postgres@localhost:5432/aigym"

    jwt_secret: str = Field(default="dev-secret-change-me")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    member_code_ttl_minutes: int = 5
    member_code_rate_limit_per_hour: int = 5

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
