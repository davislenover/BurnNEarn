"""Tests for the migration history, and that it builds the tables the
models describe."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.orm import Session

from app.core.db import Base
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


def test_migrations_match_the_models(db_session: Session) -> None:
    context = MigrationContext.configure(db_session.connection())

    # A difference would go into the next --autogenerate migration, such
    # as one that drops every column's time zone.
    assert compare_metadata(context, Base.metadata) == []
