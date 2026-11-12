"""Add daily activity totals and their plausibility checks.

Revision ID: activity_0001
Revises: market_0002
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "activity_0001"
down_revision: str | Sequence[str] | None = "market_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "activity_daily_totals",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("activity_date", sa.Date(), nullable=False),
        sa.Column("activity_type", sa.String(length=5), nullable=False),
        sa.Column("step_count", sa.BigInteger(), nullable=False),
        sa.Column("counted", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "activity_type = 'steps'",
            name=op.f("ck_activity_daily_totals_activity_type_valid"),
        ),
        sa.CheckConstraint(
            "counted = (step_count <= 150000)",
            name=op.f("ck_activity_daily_totals_counted_matches_plausibility"),
        ),
        sa.CheckConstraint(
            "step_count >= 0",
            name=op.f("ck_activity_daily_totals_step_count_not_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_activity_daily_totals_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            "activity_date",
            "activity_type",
            name=op.f("pk_activity_daily_totals"),
        ),
    )


def downgrade() -> None:
    op.drop_table("activity_daily_totals")
