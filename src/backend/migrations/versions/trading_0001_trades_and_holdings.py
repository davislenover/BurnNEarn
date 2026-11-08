"""Add the trades and holdings tables: every buy, and the shares each
portfolio holds.

Revision ID: trading_0001
Revises: wallet_0001
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "trading_0001"
down_revision: str | Sequence[str] | None = "wallet_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "holdings",
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "quantity >= 0", name=op.f("ck_holdings_quantity_not_negative")
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.asset_id"],
            name=op.f("fk_holdings_asset_id_assets"),
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.portfolio_id"],
            name=op.f("fk_holdings_portfolio_id_portfolios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "portfolio_id", "asset_id", name=op.f("pk_holdings")
        ),
    )
    op.create_table(
        "trades",
        sa.Column(
            "trade_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("trade_type", sa.String(length=4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "unit_price", sa.Numeric(precision=12, scale=4), nullable=False
        ),
        sa.Column(
            "currency_amount",
            sa.Numeric(precision=16, scale=4),
            nullable=False,
        ),
        sa.Column(
            "cash_balance_after",
            sa.Numeric(precision=16, scale=4),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("balance_change_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "cash_balance_after >= 0 AND cash_balance_after <> 'NaN'",
            name=op.f("ck_trades_cash_balance_after_not_negative"),
        ),
        sa.CheckConstraint(
            "status = 'executed'", name=op.f("ck_trades_status_valid")
        ),
        sa.CheckConstraint(
            "trade_type = 'buy'", name=op.f("ck_trades_trade_type_valid")
        ),
        sa.CheckConstraint(
            "unit_price > 0 AND unit_price <> 'NaN'",
            name=op.f("ck_trades_unit_price_positive"),
        ),
        sa.CheckConstraint(
            "currency_amount = quantity * unit_price",
            name=op.f("ck_trades_amount_matches"),
        ),
        sa.CheckConstraint(
            "quantity > 0", name=op.f("ck_trades_quantity_positive")
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.asset_id"],
            name=op.f("fk_trades_asset_id_assets"),
        ),
        sa.ForeignKeyConstraint(
            ["balance_change_id"],
            ["balance_changes.balance_change_id"],
            name=op.f("fk_trades_balance_change_id_balance_changes"),
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.portfolio_id"],
            name=op.f("fk_trades_portfolio_id_portfolios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("trade_id", name=op.f("pk_trades")),
        sa.UniqueConstraint(
            "balance_change_id", name=op.f("uq_trades_balance_change_id")
        ),
        sa.UniqueConstraint(
            "portfolio_id",
            "request_id",
            name=op.f("uq_trades_portfolio_id_request_id"),
        ),
    )


def downgrade() -> None:
    op.drop_table("trades")
    op.drop_table("holdings")
