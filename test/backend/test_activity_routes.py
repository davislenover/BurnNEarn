"""Step sync's HTTP contract, saved totals and wallet payments."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.activity.models import ActivityDailyTotal
from app.activity.schemas import MAX_STORED_STEPS
from app.core.db import SessionLocal
from app.main import app
from app.users.types import DEMO_USER_ID, CurrentUser
from app.wallet.interface import delete_portfolio
from app.wallet.models import BalanceChange
from app.wallet.queries import activity_paid, get_balance

MakePortfolio = Callable[..., Any]
AsUser = Callable[[CurrentUser], None]
SetTime = Callable[[datetime], None]
PATH = "/v1/me/activity/daily-totals"
NOW = datetime(2026, 11, 12, 15, tzinfo=UTC)
DAY = NOW.date()


def total(steps: object = 8421, day: date = DAY) -> dict[str, object]:
    return {
        "activity_date": day.isoformat(),
        "activity_type": "steps",
        "step_count": steps,
    }


def body(*totals: dict[str, object], **changes: object) -> dict[str, object]:
    return {"time_zone": "America/Toronto", "totals": list(totals), **changes}


@pytest.fixture
def owner(
    make_portfolio: MakePortfolio, as_user: AsUser, at_time: SetTime
) -> Any:
    made = make_portfolio()
    as_user(made.user)
    at_time(NOW)
    return made


def stored(
    session: Session, owner: Any, day: date = DAY
) -> ActivityDailyTotal:
    row = session.get(
        ActivityDailyTotal,
        (owner.user.user_id, day, "steps"),
        populate_existing=True,
    )
    assert row is not None
    return row


def test_a_repeat_only_pays_the_difference_and_never_takes_money_back(
    client: TestClient, db_session: Session, owner: Any, at_time: SetTime
) -> None:
    for index, (steps, reward, credited, balance) in enumerate(
        [
            (8421, 84, 84, 84),
            (8421, 84, 0, 84),
            (8500, 85, 1, 85),
            (8000, 80, 0, 85),
            (200_000, 0, 0, 85),
            (8600, 86, 1, 86),
        ]
    ):
        now = NOW + timedelta(minutes=index)
        at_time(now)
        response = client.put(PATH, json=body(total(steps)))
        assert response.status_code == 200
        assert response.json() == {
            "totals": [
                {
                    **total(steps),
                    "counted": steps <= 150_000,
                    "reward": f"{reward:.4f}",
                    "credited_now": f"{credited:.4f}",
                }
            ],
            "cash_balance": f"{balance:.4f}",
        }
        assert get_balance(db_session, owner.portfolio_id) == balance
        row = stored(db_session, owner)
        assert row.step_count == steps
        assert row.counted == (steps <= 150_000)
        assert row.updated_at == now
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityDailyTotal))
        == 1
    )
    assert (
        db_session.scalar(
            select(func.count()).where(
                BalanceChange.portfolio_id == owner.portfolio_id
            )
        )
        == 3
    )


@pytest.mark.parametrize(
    ("steps", "paid", "counted"),
    [
        (0, 0, True),
        (99, 0, True),
        (40_000, 300, True),
        (150_000, 300, True),
        (150_001, 0, False),
        (200_000, 0, False),
        (MAX_STORED_STEPS, 0, False),
    ],
)
def test_reward_boundaries_are_saved(
    client: TestClient,
    db_session: Session,
    owner: Any,
    steps: int,
    paid: int,
    counted: bool,
) -> None:
    response = client.put(PATH, json=body(total(steps)))
    assert response.status_code == 200
    assert response.json() == {
        "totals": [
            {
                **total(steps),
                "counted": counted,
                "reward": f"{paid:.4f}",
                "credited_now": f"{paid:.4f}",
            }
        ],
        "cash_balance": f"{paid:.4f}",
    }
    assert activity_paid(db_session, owner.portfolio_id, DAY) == paid
    assert stored(db_session, owner).counted is counted


def test_a_week_is_paid_per_date_and_committed(
    client: TestClient, db_session: Session, owner: Any
) -> None:
    totals = [total(8421, DAY - timedelta(days=i)) for i in range(7)]
    response = client.put(PATH, json=body(*totals))
    assert response.status_code == 200
    assert response.json() == {
        "totals": [
            {
                **sent,
                "counted": True,
                "reward": "84.0000",
                "credited_now": "84.0000",
            }
            for sent in totals
        ],
        "cash_balance": "588.0000",
    }
    assert get_balance(db_session, owner.portfolio_id) == 7 * 84
    for i in range(7):
        assert (
            activity_paid(
                db_session, owner.portfolio_id, DAY - timedelta(days=i)
            )
            == 84
        )
    # The client rolls back after each request. A forgotten route commit
    # would have removed all the rows before these assertions.
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityDailyTotal))
        == 7
    )


def test_mixed_days_report_their_own_rewards_and_keep_request_order(
    client: TestClient,
    db_session: Session,
    make_portfolio: MakePortfolio,
    as_user: AsUser,
    at_time: SetTime,
) -> None:
    owner = make_portfolio(Decimal("50.1234"))
    as_user(owner.user)
    at_time(NOW)
    totals = [
        total(40_000, DAY - timedelta(days=2)),
        total(200_000, DAY),
        total(8421, DAY - timedelta(days=1)),
        total(99, DAY - timedelta(days=6)),
    ]
    for retry in [False, True]:
        response = client.put(PATH, json=body(*totals))
        assert response.status_code == 200
        assert response.json() == {
            "totals": [
                {
                    **sent,
                    "counted": counted,
                    "reward": reward,
                    "credited_now": "0.0000" if retry else reward,
                }
                for sent, counted, reward in zip(
                    totals,
                    [True, False, True, True],
                    ["300.0000", "0.0000", "84.0000", "0.0000"],
                    strict=True,
                )
            ],
            "cash_balance": "434.1234",
        }
    empty = client.put(PATH, json=body())
    assert empty.status_code == 200
    assert empty.json() == {"totals": [], "cash_balance": "434.1234"}
    assert get_balance(db_session, owner.portfolio_id) == Decimal("434.1234")


@pytest.mark.parametrize("offset", [-8, -7, 1])
def test_an_out_of_range_date_refuses_the_whole_batch(
    client: TestClient, db_session: Session, owner: Any, offset: int
) -> None:
    response = client.put(
        PATH, json=body(total(), total(9000, DAY + timedelta(days=offset)))
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "activity_date_out_of_range"
    assert get_balance(db_session, owner.portfolio_id) == 0
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityDailyTotal))
        == 0
    )


@pytest.mark.parametrize(
    ("zone", "day", "accepted"),
    [
        ("America/Toronto", date(2026, 11, 11), True),
        ("America/Toronto", date(2026, 11, 5), True),
        ("America/Toronto", date(2026, 11, 12), False),
        ("Asia/Tokyo", date(2026, 11, 12), True),
        ("Asia/Tokyo", date(2026, 11, 5), False),
    ],
)
def test_allowed_days_use_the_sent_zone_at_utc_midnight(
    client: TestClient,
    owner: Any,
    at_time: SetTime,
    zone: str,
    day: date,
    accepted: bool,
) -> None:
    at_time(datetime(2026, 11, 12, 0, 30, tzinfo=UTC))
    response = client.put(PATH, json=body(total(day=day), time_zone=zone))
    assert response.status_code == (200 if accepted else 422)


@pytest.mark.parametrize(
    "sent",
    [
        body(total(-1)),
        body(total(1.5)),
        body(total(1.0)),
        body(total("100")),
        body(total(True)),
        body(total(None)),
        body(total(MAX_STORED_STEPS + 1)),
        body({**total(), "activity_type": "cycling"}),
        body({**total(), "activity_date": "not-a-date"}),
        body({**total(), "counted": True}),
        body(total(), user_id=str(DEMO_USER_ID)),
        body(total(), cash_balance="999"),
        body(total(), time_zone="Not/AZone"),
        body(total(), time_zone="../UTC"),
        body(total(), total()),
        body(*(total(day=DAY - timedelta(days=i)) for i in range(8))),
        {"totals": [total()]},
        {"time_zone": "UTC"},
    ],
)
def test_bad_requests_save_nothing(
    client: TestClient,
    db_session: Session,
    owner: Any,
    sent: dict[str, object],
) -> None:
    response = client.put(PATH, json=sent)
    assert response.status_code == 422
    assert get_balance(db_session, owner.portfolio_id) == 0
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityDailyTotal))
        == 0
    )


def test_an_empty_batch_is_a_successful_no_op(
    client: TestClient, db_session: Session, owner: Any
) -> None:
    response = client.put(PATH, json=body())
    assert response.status_code == 200
    assert response.json() == {"totals": [], "cash_balance": "0.0000"}
    assert get_balance(db_session, owner.portfolio_id) == 0


def test_anonymous_requests_are_refused(client: TestClient) -> None:
    assert client.put(PATH, json=body(total())).status_code == 401


def test_users_get_separate_totals_and_payments(
    client: TestClient,
    db_session: Session,
    owner: Any,
    make_portfolio: MakePortfolio,
    as_user: AsUser,
) -> None:
    other = make_portfolio()
    assert client.put(PATH, json=body(total())).status_code == 200
    as_user(other.user)
    assert client.put(PATH, json=body(total(8500))).status_code == 200
    assert stored(db_session, owner).step_count == 8421
    assert stored(db_session, other).step_count == 8500
    assert get_balance(db_session, owner.portfolio_id) == 84
    assert get_balance(db_session, other.portfolio_id) == 85


def test_a_payment_failure_rolls_back_the_whole_batch(
    client: TestClient,
    db_session: Session,
    owner: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.activity.service as service

    pay = service.change_balance
    calls = 0

    def fail_second(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("payment failed")
        return pay(*args, **kwargs)

    monkeypatch.setattr(service, "change_balance", fail_second)
    with pytest.raises(RuntimeError, match="payment failed"):
        client.put(
            PATH, json=body(total(), total(day=DAY - timedelta(days=1)))
        )
    assert calls == 2
    assert get_balance(db_session, owner.portfolio_id) == 0
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityDailyTotal))
        == 0
    )
    assert (
        db_session.scalar(
            select(func.count()).where(
                BalanceChange.portfolio_id == owner.portfolio_id
            )
        )
        == 0
    )


def test_a_demo_week_is_persisted_and_retry_does_not_pay_twice(
    database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Real request sessions and the demo-user dependency, on the dedicated
    # test database. Unlike client, these commits cross connections.
    from app.core.clock import get_clock
    from app.scripts.seed_demo import seed
    from app.users.models import User
    from app.users.settings import get_user_settings

    with SessionLocal() as session:
        portfolio_id = seed(session)
        session.commit()
    monkeypatch.setenv("DEMO_USER_ENABLED", "true")
    get_user_settings.cache_clear()
    app.dependency_overrides[get_clock] = lambda: lambda: NOW
    try:
        sent = body(*(total(day=DAY - timedelta(days=i)) for i in range(7)))
        with TestClient(app) as demo:
            for credited in ["84.0000", "0.0000"]:
                response = demo.put(PATH, json=sent)
                assert response.status_code == 200
                reply = response.json()
                assert reply["cash_balance"] == "588.0000"
                assert len(reply["totals"]) == 7
                assert all(
                    day["credited_now"] == credited for day in reply["totals"]
                )
        with SessionLocal() as session:
            assert get_balance(session, portfolio_id) == Decimal(588)
            assert (
                session.scalar(
                    select(func.count()).where(
                        ActivityDailyTotal.user_id == DEMO_USER_ID
                    )
                )
                == 7
            )
    finally:
        app.dependency_overrides.clear()
        get_user_settings.cache_clear()
        with SessionLocal() as session:
            delete_portfolio(session, portfolio_id)
            demo_user = session.get(User, DEMO_USER_ID)
            if demo_user is not None:
                session.delete(demo_user)
            session.commit()
