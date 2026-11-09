"""Configuration read from environment variables or a local .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend settings. Each field can be set by an environment variable
    of the same name in upper case, for example DATABASE_URL."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://fitfolio:fitfolio@localhost:5432/fitfolio"
    )


@lru_cache
def get_settings() -> Settings:
    """Return the settings, read once per process."""
    return Settings()
