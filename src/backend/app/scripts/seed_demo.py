"""Set up the PoC's demo user and their live portfolio.

Run from src/backend:

    uv run python -m app.scripts.seed_demo
    uv run python -m app.scripts.seed_demo reset

It uses only the users and wallet interfaces, never their tables.
"""

import sys
import uuid

from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.users.interface import create_user
from app.users.types import DEMO_USER_ID
from app.wallet.interface import create_live_portfolio, delete_portfolio
from app.wallet.queries import live_portfolio_id

USAGE = "Usage: python -m app.scripts.seed_demo [reset]"


def seed(session: Session) -> uuid.UUID:
    """Add the demo user and their live portfolio if they don't exist yet,
    and return the portfolio's ID. Running it again changes nothing.

    Never commits.
    """
    existing = _demo_portfolio_id(session)
    if existing is not None:
        return existing
    _add_demo_user(session)
    return create_live_portfolio(session, DEMO_USER_ID)


def reset(session: Session) -> uuid.UUID:
    """Give the demo user a fresh live portfolio at 0, and return its ID.

    Deleting the old portfolio also deletes everything under it, such as its
    balance changes. Never commits.
    """
    existing = _demo_portfolio_id(session)
    if existing is None:
        _add_demo_user(session)
    else:
        delete_portfolio(session, existing)
    return create_live_portfolio(session, DEMO_USER_ID)


def _demo_portfolio_id(session: Session) -> uuid.UUID | None:
    try:
        return live_portfolio_id(session, DEMO_USER_ID)
    except NoResultFound:
        return None


def _add_demo_user(session: Session) -> None:
    # The demo user can exist without a portfolio, such as after a failed
    # run. Adding them inside a savepoint undoes only that one insert.
    try:
        with session.begin_nested():
            create_user(session, DEMO_USER_ID)
    except IntegrityError:
        pass


def main(argv: list[str]) -> int:
    if argv not in ([], ["reset"]):
        print(USAGE, file=sys.stderr)
        return 2
    with SessionLocal() as session:
        portfolio_id = reset(session) if argv else seed(session)
        session.commit()
    action = "Reset" if argv else "Ready"
    print(f"{action}: demo user {DEMO_USER_ID}, portfolio {portfolio_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
