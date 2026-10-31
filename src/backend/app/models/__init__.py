"""Table models. Import every model module here so Alembic sees it."""

from app.models.asset import Asset, AssetType
from app.models.price import Price

__all__ = ["Asset", "AssetType", "Price"]
