"""The request and reply of PUT /v1/me/activity/daily-totals."""

from datetime import date
from typing import Literal, Self
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.core.constants import SYNC_LOOKBACK_PERIOD
from app.core.money import Money

# PostgreSQL BIGINT's largest value. Implausible totals are still stored,
# but values the column cannot hold must be refused before any write.
MAX_STORED_STEPS = 2**63 - 1


class DailyTotal(BaseModel):
    """One date's total from the phone, not an increment."""

    model_config = ConfigDict(extra="forbid")

    activity_date: date
    activity_type: Literal["steps"]
    step_count: int = Field(ge=0, le=MAX_STORED_STEPS, strict=True)


class DailyTotalsRequest(BaseModel):
    """At most one total per date, for at most one week."""

    model_config = ConfigDict(extra="forbid")

    time_zone: str
    totals: list[DailyTotal] = Field(max_length=SYNC_LOOKBACK_PERIOD.days)

    @field_validator("time_zone")
    @classmethod
    def real_time_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ValueError, KeyError) as error:
            raise ValueError("Unknown time zone") from error
        return value

    @model_validator(mode="after")
    def unique_dates(self) -> Self:
        dates = [total.activity_date for total in self.totals]
        if len(dates) != len(set(dates)):
            raise ValueError("Each activity date may appear only once")
        return self


class DailyTotalResult(BaseModel):
    """One submitted day's total, reward and payment from this sync."""

    model_config = ConfigDict(frozen=True)

    activity_date: date
    activity_type: Literal["steps"]
    step_count: int
    counted: bool
    reward: Money
    credited_now: Money


class DailyTotalsResponse(BaseModel):
    """Results in request order, and the balance after all top-ups."""

    totals: list[DailyTotalResult]
    cash_balance: Money
