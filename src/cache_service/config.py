"""Service configuration: nothing else reads os.environ directly."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CACHE_",
        env_file=".env",
        extra="ignore",
    )

    # SQLite by default so the service runs with no infrastructure.
    database_url: str = "sqlite+aiosqlite:///./cache.db"
    transformer_latency_ms: int = 50


settings = Settings()
