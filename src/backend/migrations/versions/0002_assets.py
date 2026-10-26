"""Add the assets table with the starting list of stocks.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Values are written out here instead of imported from the app, so this
# migration always does the same thing even if the app changes later.
STARTING_STOCKS = [
    ("AAPL", "Apple Inc."),
    ("MSFT", "Microsoft Corporation"),
    ("GOOGL", "Alphabet Inc. Class A"),
    ("AMZN", "Amazon.com, Inc."),
    ("NVDA", "NVIDIA Corporation"),
    ("META", "Meta Platforms, Inc."),
    ("TSLA", "Tesla, Inc."),
    ("JPM", "JPMorgan Chase & Co."),
    ("V", "Visa Inc."),
    ("AMD", "Advanced Micro Devices, Inc."),
]


def upgrade() -> None:
    assets = op.create_table(
        "assets",
        sa.Column(
            "asset_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("asset_type", sa.String(length=5), nullable=False),
        sa.Column(
            "price_currency",
            sa.String(length=3),
            server_default="USD",
            nullable=False,
        ),
        sa.Column(
            "is_tradable", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "asset_type IN ('stock', 'etf')",
            name=op.f("ck_assets_asset_type_valid"),
        ),
        sa.CheckConstraint(
            "price_currency = 'USD'", name=op.f("ck_assets_one_currency")
        ),
        sa.PrimaryKeyConstraint("asset_id", name=op.f("pk_assets")),
        sa.UniqueConstraint("symbol", name=op.f("uq_assets_symbol")),
    )
    op.bulk_insert(
        assets,
        [
            {"symbol": symbol, "name": name, "asset_type": "stock"}
            for symbol, name in STARTING_STOCKS
        ],
    )


def downgrade() -> None:
    op.drop_table("assets")
