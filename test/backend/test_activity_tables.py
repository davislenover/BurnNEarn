"""Rules PostgreSQL keeps even when a caller skips request validation."""

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.activity.models import ActivityDailyTotal
from app.users.models import User


def values(owner_id: uuid.UUID, **changes: object) -> dict[str, object]:
    return {
        "user_id": owner_id,
        "activity_date": date(2026, 11, 12),
        "activity_type": "steps",
        "step_count": 8421,
        "counted": True,
        "updated_at": datetime(2026, 11, 12, 15, tzinfo=UTC),
        **changes,
    }


def user(session: Session) -> User:
    made = User(time_zone="America/Toronto")
    session.add(made)
    session.flush()
    return made


@pytest.mark.parametrize(
    ("changes", "rule"),
    [
        ({"step_count": -1}, "step_count_not_negative"),
        ({"activity_type": "other"}, "activity_type_valid"),
        ({"step_count": 200_000}, "counted_matches_plausibility"),
        ({"counted": False}, "counted_matches_plausibility"),
        ({"user_id": uuid.uuid4()}, "fk_activity_daily_totals_user_id_users"),
    ],
)
def test_invalid_rows_are_refused(
    db_session: Session, changes: dict[str, object], rule: str
) -> None:
    owner = user(db_session)
    with pytest.raises(IntegrityError, match=rule):
        db_session.execute(
            insert(ActivityDailyTotal).values(values(owner.user_id, **changes))
        )


def test_each_user_date_and_type_has_only_one_row(db_session: Session) -> None:
    owner = user(db_session)
    row = values(owner.user_id)
    db_session.execute(insert(ActivityDailyTotal).values(row))
    with pytest.raises(IntegrityError, match="pk_activity_daily_totals"):
        db_session.execute(insert(ActivityDailyTotal).values(row))


def test_totals_are_deleted_with_the_user(db_session: Session) -> None:
    owner = user(db_session)
    db_session.execute(
        insert(ActivityDailyTotal).values(values(owner.user_id))
    )
    db_session.delete(owner)
    db_session.flush()
    assert (
        db_session.scalar(
            select(ActivityDailyTotal).where(
                ActivityDailyTotal.user_id == owner.user_id
            )
        )
        is None
    )
