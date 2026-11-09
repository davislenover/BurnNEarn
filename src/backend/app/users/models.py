"""The users module's table: one row per user (SRS Section 7.2)."""

import uuid
from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class User(Base):
    """One user. Sign-in fields come later, with real accounts."""

    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    # An IANA time zone name, such as "America/Toronto". Nothing reads it
    # yet. Activity (#190) counts each day in the zone the phone sends with
    # each sync, since a day follows where the user is (SEC-23).
    time_zone: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
