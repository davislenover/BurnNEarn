"""Activity's table. Other modules' tables are referenced only by name."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import MAX_DAILY_STEPS
from app.core.db import Base


class ActivityDailyTotal(Base):
    """The latest total received for one user's date and activity type."""

    __tablename__ = "activity_daily_totals"
    __table_args__ = (
        CheckConstraint("activity_type = 'steps'", name="activity_type_valid"),
        CheckConstraint("step_count >= 0", name="step_count_not_negative"),
        CheckConstraint(
            f"counted = (step_count <= {MAX_DAILY_STEPS})",
            name="counted_matches_plausibility",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    activity_date: Mapped[date] = mapped_column(primary_key=True)
    activity_type: Mapped[str] = mapped_column(String(5), primary_key=True)
    step_count: Mapped[int] = mapped_column(BigInteger)
    counted: Mapped[bool]
    # Set from the injected clock on every sync, including a repeat.
    updated_at: Mapped[datetime]
