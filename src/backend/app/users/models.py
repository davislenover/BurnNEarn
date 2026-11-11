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
    # yet. The phone puts each activity record on its day (SEC-23, HA H51),
    # so the server will use this zone only to find the user's date, to
    # refuse a daily total dated in the future (SEC-24).
    time_zone: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
