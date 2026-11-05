"""Add the provider_requests table: one row per call to the market data
provider, to watch its request limit.

Revision ID: market_0001
Revises: 0003
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "market_0001"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_requests",
        sa.Column(
            "provider_request_id",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("outcome", sa.String(length=14), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('ok', 'rate_limited', 'unknown_symbol', 'error')",
            name=op.f("ck_provider_requests_outcome_valid"),
        ),
        sa.PrimaryKeyConstraint(
            "provider_request_id", name=op.f("pk_provider_requests")
        ),
    )
    op.create_index(
        op.f("ix_provider_requests_requested_at"),
        "provider_requests",
        ["requested_at"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_provider_requests_requested_at"),
        table_name="provider_requests",
    )
    op.drop_table("provider_requests")
