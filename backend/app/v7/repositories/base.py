"""Base repository class."""
from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.base import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations."""

    def __init__(self, model: type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get(self, obj_id: uuid.UUID) -> ModelType | None:
        """Get object by ID."""
        result = await self.db.execute(
            select(self.model).where(self.model.id == obj_id)
        )
        return result.scalar_one_or_none()

    async def get_or_404(self, obj_id: uuid.UUID) -> ModelType:
        """Get object by ID or raise 404."""
        obj = await self.get(obj_id)
        if not obj:
            raise ValueError(f"{self.model.__name__} not found: {obj_id}")
        return obj

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        order_desc: bool = False,
    ) -> list[ModelType]:
        """List objects with pagination and filters."""
        query = select(self.model)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)

        if order_by and hasattr(self.model, order_by):
            order_col = getattr(self.model, order_by)
            query = query.order_by(order_col.desc() if order_desc else order_col)
        else:
            query = query.order_by(self.model.created_at.desc())

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Count objects with filters."""
        query = select(func.count()).select_from(self.model)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)

        result = await self.db.execute(query)
        return result.scalar_one()

    async def create(self, data: dict[str, Any]) -> ModelType:
        """Create a new object."""
        obj = self.model(**data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj_id: uuid.UUID, data: dict[str, Any]) -> ModelType:
        """Update an object."""
        obj = await self.get_or_404(obj_id)
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj_id: uuid.UUID) -> None:
        """Delete an object."""
        obj = await self.get_or_404(obj_id)
        await self.db.delete(obj)
        await self.db.flush()

    async def exists(self, obj_id: uuid.UUID) -> bool:
        """Check if object exists."""
        obj = await self.get(obj_id)
        return obj is not None
