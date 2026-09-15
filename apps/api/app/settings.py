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

    # 32+ bytes: PyJWT warns below that for HS256. Never use this default in
    # production — Railway gets its own generated secret (stage 7).
    jwt_secret: str = Field(default="dev-secret-change-me-32-bytes-minimum")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    member_code_ttl_minutes: int = 5
    member_code_rate_limit_per_hour: int = 5

    # Shared secret required on the gym-onboarding endpoint. There is no
    # staff JWT yet at that point — this is the only thing standing between
    # POST /gyms and anyone on the internet creating a tenant.
    onboarding_secret: str = Field(default="dev-onboarding-secret-change-me")

    # Optional fallback PIN scripts/seed.py hashes onto a staff row that
    # doesn't have one yet (unset here, so a fresh clone/CI database never
    # gets a real credential). Never overwrites a pin_hash that's already
    # set — see the seed() docstring.
    seed_manager_pin: str | None = None

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
