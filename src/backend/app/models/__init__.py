"""Table models. Import every model module here so Alembic sees it."""

from app.models.asset import Asset, AssetType

__all__ = ["Asset", "AssetType"]
