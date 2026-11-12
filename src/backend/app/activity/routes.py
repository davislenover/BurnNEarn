"""Activity's HTTP route: save steps and award their currency."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.activity.schemas import DailyTotalsRequest
from app.activity.service import sync_daily_totals
from app.core.clock import Clock, get_clock
from app.core.db import get_db
from app.users.interface import get_current_user
from app.users.types import CurrentUser
from app.wallet.interface import lock_live_portfolio

router = APIRouter(tags=["activity"])


@router.put(
    "/me/activity/daily-totals",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def put_daily_totals(
    request: DailyTotalsRequest,
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    """Save a week of totals and pay any top-ups in one transaction.

    A success has no body. A repeat pays nothing twice.
    """
    locked = lock_live_portfolio(db, user.user_id)
    sync_daily_totals(db, locked, request, clock())
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
