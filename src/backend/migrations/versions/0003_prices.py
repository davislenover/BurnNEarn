"""Add the prices table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prices",
        sa.Column("price_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column(
            "price_currency",
            sa.String(length=3),
            server_default="USD",
            nullable=False,
        ),
        sa.Column("quoted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "obtained_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint("price > 0", name=op.f("ck_prices_price_positive")),
        sa.CheckConstraint(
            "price_currency = 'USD'", name=op.f("ck_prices_one_currency")
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.asset_id"],
            name=op.f("fk_prices_asset_id_assets"),
        ),
        sa.PrimaryKeyConstraint("price_id", name=op.f("pk_prices")),
        sa.UniqueConstraint(
            "asset_id",
            "quoted_at",
            name=op.f("uq_prices_asset_id_quoted_at"),
        ),
    )


def downgrade() -> None:
    op.drop_table("prices")
