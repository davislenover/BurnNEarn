"""What other modules may call in users."""

import uuid
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy.orm import Session

from app.users.models import User
from app.users.settings import UserSettings, get_user_settings
from app.users.types import DEMO_USER_ID, CurrentUser, NotAuthenticatedError

__all__ = ["create_user", "get_current_user"]

# The team and its first users are in Ontario.
DEFAULT_TIME_ZONE = "America/Toronto"


def get_current_user(
    settings: UserSettings = Depends(get_user_settings),
) -> CurrentUser:
    """FastAPI dependency for every route that needs a user.

    The phone never sends a user ID. In the PoC every request is the demo
    user when DEMO_USER_ENABLED is on, and is refused with 401 otherwise.
    Real sign-in later only changes the inside of this function. A test
    picks the user by replacing it in app.dependency_overrides.
    """
    if not settings.demo_user_enabled:
        raise NotAuthenticatedError()
    return CurrentUser(user_id=DEMO_USER_ID)


def create_user(
    session: Session,
    user_id: uuid.UUID | None = None,
    time_zone: str = DEFAULT_TIME_ZONE,
) -> uuid.UUID:
    """Add a user and return their ID. Never commits.

    The seed script passes DEMO_USER_ID. Without a user_id the database
    makes a new one. Raises ValueError for a time zone that doesn't exist,
    so a stored zone always works for whatever reads it later.
    """
    try:
        ZoneInfo(time_zone)
    except (ValueError, KeyError) as error:
        raise ValueError(f"Unknown time zone: {time_zone}") from error
    user = User(time_zone=time_zone)
    if user_id is not None:
        user.user_id = user_id
    session.add(user)
    session.flush()
    return user.user_id
