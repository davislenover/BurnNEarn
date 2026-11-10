"""Refuse a NaN price. PostgreSQL counts NaN as above every number, so
price > 0 alone let it through.

Revision ID: market_0002
Revises: trading_0001
Create Date: 2026-11-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "market_0002"
down_revision: str | Sequence[str] | None = "trading_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The full name, so the naming convention leaves it as it is.
NAME = "ck_prices_price_positive"


def upgrade() -> None:
    op.drop_constraint(op.f(NAME), "prices", type_="check")
    op.create_check_constraint(
        op.f(NAME), "prices", "price > 0 AND price <> 'NaN'"
    )


def downgrade() -> None:
    op.drop_constraint(op.f(NAME), "prices", type_="check")
    op.create_check_constraint(op.f(NAME), "prices", "price > 0")
