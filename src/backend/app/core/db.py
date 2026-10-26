"""Database engine, sessions and the base class for table models."""

from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import DateTime, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.settings import get_settings

# Gives every index and constraint a predictable name, so migrations can
# refer to them by name later.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all table models. Alembic reads its metadata."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Store every timestamp with its time zone (timestamptz), so times from
    # different users and the server compare correctly.
    type_annotation_map = {datetime: DateTime(timezone=True)}


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that gives each request its own session."""
    with SessionLocal() as session:
        yield session
