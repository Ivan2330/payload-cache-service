"""Service configuration.

Everything that differs between a laptop and a deployment lives here, so the
code never reads os.environ directly and tests can override a single object.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CACHE_",
        env_file=".env",
        extra="ignore",
    )

    # SQLite keeps the service runnable with no infrastructure; switching to
    # PostgreSQL is a URL change, because every query is plain SQLAlchemy.
    database_url: str = "sqlite+aiosqlite:///./cache.db"

    # The transformer stands in for a remote service. The delay makes the cost
    # of a cache miss visible when the CLI runs with --repeat.
    transformer_latency_ms: int = 50


settings = Settings()
