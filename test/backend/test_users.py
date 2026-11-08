"""Tests for the users module: the current user and create_user."""

import uuid

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.plugins import Plugin
from app.main import create_app
from app.users.interface import create_user, get_current_user
from app.users.models import User
from app.users.settings import UserSettings, get_user_settings
from app.users.types import DEMO_USER_ID, CurrentUser


def who_is_calling(demo_user_enabled: bool) -> TestClient:
    """A small app with one route that needs a user."""
    router = APIRouter()

    @router.get("/me")
    def me(user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
        return {"user_id": str(user.user_id)}

    app = create_app([Plugin(name="probe", router=router)])
    app.dependency_overrides[get_user_settings] = lambda: UserSettings(
        _env_file=None, demo_user_enabled=demo_user_enabled
    )
    return TestClient(app)


def test_every_request_is_the_demo_user_when_it_is_on() -> None:
    response = who_is_calling(demo_user_enabled=True).get("/v1/me")

    assert response.status_code == 200
    assert response.json() == {"user_id": str(DEMO_USER_ID)}


def test_a_request_is_refused_when_the_demo_user_is_off() -> None:
    response = who_is_calling(demo_user_enabled=False).get("/v1/me")

    assert response.status_code == 401
    assert response.json() == {
        "detail": {
            "code": "not_authenticated",
            "message": "Sign in to continue.",
        }
    }


def test_the_demo_user_is_off_unless_a_setting_turns_it_on() -> None:
    assert UserSettings(_env_file=None).demo_user_enabled is False


def test_create_user_adds_one_user(db_session: Session) -> None:
    user_id = create_user(db_session)

    user = db_session.get(User, user_id)
    assert user is not None
    assert user.time_zone == "America/Toronto"


def test_create_user_can_use_a_given_id_and_time_zone(
    db_session: Session,
) -> None:
    user_id = create_user(db_session, DEMO_USER_ID, "America/Vancouver")

    assert user_id == DEMO_USER_ID
    assert (
        db_session.scalar(
            select(User.time_zone).where(User.user_id == DEMO_USER_ID)
        )
        == "America/Vancouver"
    )


@pytest.mark.parametrize("time_zone", ["Mars/Olympus", "../etc", ""])
def test_create_user_refuses_a_time_zone_that_does_not_exist(
    db_session: Session, time_zone: str
) -> None:
    with pytest.raises(ValueError, match="time zone"):
        create_user(db_session, uuid.uuid4(), time_zone)

    assert db_session.scalars(select(User)).all() == []
