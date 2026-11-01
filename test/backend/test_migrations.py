"""Tests for the migration history itself. No database is needed."""

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migrations_have_one_head(alembic_config: Config) -> None:
    heads = ScriptDirectory.from_config(alembic_config).get_heads()

    assert len(heads) == 1, (
        f"Found {len(heads)} newest migrations: {heads}. Two migrations "
        "claim to come next. Point the newer one's down_revision at main's "
        "newest migration and give it the next number."
    )
