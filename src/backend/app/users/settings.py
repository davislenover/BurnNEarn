"""The users module's settings, read from environment variables or .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class UserSettings(BaseSettings):
    """Each field is set by the environment variable of the same name in
    upper case, for example DEMO_USER_ENABLED."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Treat every request as coming from the demo user. The PoC has no
    # sign-in, so routes that need a user only work with this on. Off by
    # default, so a server never runs as the demo user by accident.
    demo_user_enabled: bool = False


@lru_cache
def get_user_settings() -> UserSettings:
    """Return the user settings, read once per process."""
    return UserSettings()
