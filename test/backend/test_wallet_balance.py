"""Tests for GET /v1/me/balance."""

from decimal import Decimal

from fastapi.testclient import TestClient

from app.users.types import DEMO_USER_ID, CurrentUser

DEMO_USER = CurrentUser(user_id=DEMO_USER_ID)


def test_the_balance_route_returns_the_demo_users_balance(
    client: TestClient, make_portfolio, as_user
) -> None:
    owner = make_portfolio(Decimal("412"), user=DEMO_USER)
    as_user(owner.user)

    response = client.get("/v1/me/balance")

    assert response.status_code == 200
    assert response.json() == {"cash_balance": "412.0000"}


def test_a_new_portfolio_shows_a_balance_of_0(
    client: TestClient, make_portfolio, as_user
) -> None:
    as_user(make_portfolio(user=DEMO_USER).user)

    response = client.get("/v1/me/balance")

    assert response.json() == {"cash_balance": "0.0000"}


def test_the_balance_route_refuses_when_the_demo_user_is_off(
    client: TestClient, make_portfolio
) -> None:
    # conftest turns the demo user off, and no as_user picks a user.
    make_portfolio(Decimal("412"), user=DEMO_USER)

    response = client.get("/v1/me/balance")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "not_authenticated"