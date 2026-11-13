"""Save daily totals and pay only what is still owed. Never commits."""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.activity.models import ActivityDailyTotal
from app.activity.rewards import allowed_dates, daily_reward, top_up
from app.activity.schemas import DailyTotalResult, DailyTotalsRequest
from app.activity.types import ActivityDateOutOfRangeError
from app.core.constants import MAX_DAILY_STEPS
from app.wallet.interface import change_balance
from app.wallet.queries import activity_paid
from app.wallet.types import BalanceChangeReason, LockedPortfolio


def sync_daily_totals(
    session: Session,
    locked: LockedPortfolio,
    request: DailyTotalsRequest,
    now: datetime,
) -> list[DailyTotalResult]:
    """Apply totals to the locked user's live portfolio (FR_ActEarn).

    The route locks first, so concurrent syncs read the preceding sync's
    payments. All dates are checked before writing any of the batch.
    """
    today = now.astimezone(ZoneInfo(request.time_zone)).date()
    allowed = allowed_dates(today)
    if any(total.activity_date not in allowed for total in request.totals):
        raise ActivityDateOutOfRangeError()

    results = []
    for total in request.totals:
        counted = total.step_count <= MAX_DAILY_STEPS
        values = {
            "step_count": total.step_count,
            "counted": counted,
            "updated_at": now,
        }
        statement = insert(ActivityDailyTotal).values(
            user_id=locked.user_id,
            activity_date=total.activity_date,
            activity_type=total.activity_type,
            **values,
        )
        session.execute(
            statement.on_conflict_do_update(
                index_elements=["user_id", "activity_date", "activity_type"],
                set_=values,
            )
        )
        reward = daily_reward(total.step_count)
        owed = top_up(
            reward,
            activity_paid(session, locked.portfolio_id, total.activity_date),
        )
        if owed > 0:
            change_balance(
                session,
                locked,
                owed,
                BalanceChangeReason.ACTIVITY_REWARD,
                total.activity_date,
            )
        results.append(
            DailyTotalResult(
                activity_date=total.activity_date,
                activity_type=total.activity_type,
                step_count=total.step_count,
                counted=counted,
                reward=reward,
                credited_now=owed,
            )
        )
    return results
