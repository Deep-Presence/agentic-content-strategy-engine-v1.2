"""Repositories for LLM cost events and model pricing."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.db.models.cost import LLMCostEventModel, ModelPricingModel
from core.db.repositories.base import SQLAlchemyRepository


class CostEventRepository(SQLAlchemyRepository[LLMCostEventModel]):
    model_class = LLMCostEventModel

    async def create_event(self, **kwargs: Any) -> LLMCostEventModel:
        return await self.create(**kwargs)

    async def bulk_create(self, events: list[dict[str, Any]]) -> int:
        """Insert multiple cost events. Returns count inserted."""
        if not events:
            return 0
        for ev in events:
            ev.setdefault("id", _uuid.uuid4())
        stmt = pg_insert(LLMCostEventModel).values(events)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount


class ModelPricingRepository(SQLAlchemyRepository[ModelPricingModel]):
    model_class = ModelPricingModel

    async def get_by_model_name(self, name: str) -> ModelPricingModel | None:
        stmt = select(ModelPricingModel).where(ModelPricingModel.model_name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_active(self) -> Sequence[ModelPricingModel]:
        stmt = (
            select(ModelPricingModel)
            .where(ModelPricingModel.is_active.is_(True))
            .order_by(ModelPricingModel.model_name)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def upsert(
        self,
        model_name: str,
        input_cost_per_1m: float,
        output_cost_per_1m: float,
        notes: str | None = None,
    ) -> ModelPricingModel:
        """Insert or update a pricing entry."""
        stmt = pg_insert(ModelPricingModel).values(
            id=_uuid.uuid4(),
            model_name=model_name,
            input_cost_per_1m=input_cost_per_1m,
            output_cost_per_1m=output_cost_per_1m,
            is_active=True,
            notes=notes,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["model_name"],
            set_={
                "input_cost_per_1m": stmt.excluded.input_cost_per_1m,
                "output_cost_per_1m": stmt.excluded.output_cost_per_1m,
                "notes": stmt.excluded.notes,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()
        # Return the row
        return await self.get_by_model_name(model_name)  # type: ignore[return-value]
