"""Tests for the migration history itself. No database is needed."""

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.settings import Settings


def test_migrations_have_one_head(alembic_config: Config) -> None:
    heads = ScriptDirectory.from_config(alembic_config).get_heads()

    assert len(heads) == 1, (
        f"Found {len(heads)} newest migrations: {heads}. Two migrations "
        "claim to come next. Point your migration's down_revision at main's "
        "newest migration, and keep its name."
    )


def test_migrations_accept_a_password_with_special_characters(
    alembic_config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "postgresql+psycopg://user:p%40ss%25word@localhost/example"
    monkeypatch.setattr(
        "app.core.settings.get_settings",
        lambda: Settings(database_url=url),
    )
    config = Config(alembic_config.config_file_name)

    # sql=True writes the SQL out instead of connecting to a database.
    command.upgrade(config, "0001", sql=True)

    assert config.get_main_option("sqlalchemy.url") == url
