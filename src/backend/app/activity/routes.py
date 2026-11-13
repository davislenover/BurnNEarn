"""Activity's HTTP route: save steps and award their currency."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.activity.schemas import DailyTotalsRequest, DailyTotalsResponse
from app.activity.service import sync_daily_totals
from app.core.clock import Clock, get_clock
from app.core.constants import EARNING_RATES, ActivityType
from app.core.db import get_db
from app.users.interface import get_current_user
from app.users.types import CurrentUser
from app.wallet.interface import lock_live_portfolio
from app.wallet.queries import get_balance

router = APIRouter(tags=["activity"])


@router.put("/me/activity/daily-totals")
def put_daily_totals(
    request: DailyTotalsRequest,
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
    user: CurrentUser = Depends(get_current_user),
) -> DailyTotalsResponse:
    """Save a week of totals and pay any top-ups in one transaction.

    Return each day's reward and top-up, the earning rate, and the balance.
    A repeat pays nothing twice and reports credited_now as zero.
    """
    locked = lock_live_portfolio(db, user.user_id)
    totals = sync_daily_totals(db, locked, request, clock())
    reply = DailyTotalsResponse(
        totals=totals,
        cash_balance=get_balance(db, locked.portfolio_id),
        steps_per_coin=EARNING_RATES[ActivityType.STEPS],
    )
    db.commit()
    return reply
