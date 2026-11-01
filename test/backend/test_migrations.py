"""Tests for the migration history itself. No database is needed."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ALEMBIC_INI = Path(__file__).parents[2] / "src" / "backend" / "alembic.ini"


def test_migrations_have_one_head() -> None:
    heads = ScriptDirectory.from_config(Config(ALEMBIC_INI)).get_heads()

    assert len(heads) == 1, (
        f"Found {len(heads)} newest migrations: {heads}. Two migrations "
        "claim to come next. Point the newer one's down_revision at main's "
        "newest migration and give it the next number."
    )
