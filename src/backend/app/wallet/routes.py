"""Wallet's HTTP route: the current user's balance."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.money import Money
from app.users.interface import get_current_user
from app.users.types import CurrentUser
from app.wallet.queries import get_balance, live_portfolio_id

router = APIRouter(tags=["wallet"])


class Balance(BaseModel):
    cash_balance: Money


@router.get("/me/balance")
def read_balance(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Balance:
    """The current user's balance in their live portfolio.

    It only reads, so it never commits.
    """
    portfolio_id = live_portfolio_id(db, user.user_id)
    return Balance(cash_balance=get_balance(db, portfolio_id))