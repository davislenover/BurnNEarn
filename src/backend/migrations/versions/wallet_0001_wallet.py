"""Add the portfolios and balance_changes tables: each user's currency, and
every change to it.

Revision ID: wallet_0001
Revises: users_0001
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "wallet_0001"
down_revision: str | Sequence[str] | None = "users_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column(
            "portfolio_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "cash_balance",
            sa.Numeric(precision=16, scale=4),
            server_default="0",
            nullable=False,
        ),
        sa.Column("scenario_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "cash_balance >= 0",
            name=op.f("ck_portfolios_cash_balance_not_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_portfolios_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("portfolio_id", name=op.f("pk_portfolios")),
    )
    op.create_index(
        "uq_portfolios_live_user_id",
        "portfolios",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("scenario_id IS NULL"),
    )
    op.create_table(
        "balance_changes",
        sa.Column(
            "balance_change_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=16, scale=4), nullable=False),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("activity_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(reason = 'activity_reward') = (activity_date IS NOT NULL)",
            name=op.f("ck_balance_changes_activity_date_only_for_rewards"),
        ),
        sa.CheckConstraint(
            "reason IN ('activity_reward', 'trade_purchase')",
            name=op.f("ck_balance_changes_reason_valid"),
        ),
        sa.CheckConstraint(
            "amount <> 0", name=op.f("ck_balance_changes_amount_not_zero")
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.portfolio_id"],
            name=op.f("fk_balance_changes_portfolio_id_portfolios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "balance_change_id", name=op.f("pk_balance_changes")
        ),
    )
    op.create_index(
        op.f("ix_balance_changes_portfolio_id"),
        "balance_changes",
        ["portfolio_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_balance_changes_portfolio_id"), table_name="balance_changes"
    )
    op.drop_table("balance_changes")
    op.drop_index("uq_portfolios_live_user_id", table_name="portfolios")
    op.drop_table("portfolios")
