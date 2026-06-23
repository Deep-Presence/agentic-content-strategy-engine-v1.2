"""Repositories for LLM cost events and model pricing."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import func, select, update
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

    async def summarize_by_agent_for_workspace(
        self,
        workspace_id: str | _uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Aggregate workspace BYOK usage by agent key."""
        wid = _uuid.UUID(str(workspace_id)) if isinstance(workspace_id, str) else workspace_id
        stmt = (
            select(
                LLMCostEventModel.agent_key,
                func.count(LLMCostEventModel.id).label("call_count"),
                func.coalesce(func.sum(LLMCostEventModel.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(LLMCostEventModel.completion_tokens), 0).label("completion_tokens"),
                func.coalesce(func.sum(LLMCostEventModel.estimated_cost_usd), 0.0).label("estimated_cost_usd"),
                func.max(LLMCostEventModel.event_time).label("last_used_at"),
            )
            .where(LLMCostEventModel.workspace_id == wid)
            .where(LLMCostEventModel.agent_key.is_not(None))
            .where(LLMCostEventModel.agent_key != "")
            .group_by(LLMCostEventModel.agent_key)
            .order_by(func.coalesce(func.sum(LLMCostEventModel.estimated_cost_usd), 0.0).desc())
        )
        result = await self._session.execute(stmt)
        return [
            {
                "agent_key": row.agent_key or "",
                "call_count": int(row.call_count or 0),
                "prompt_tokens": int(row.prompt_tokens or 0),
                "completion_tokens": int(row.completion_tokens or 0),
                "estimated_cost_usd": float(row.estimated_cost_usd or 0.0),
                "last_used_at": row.last_used_at,
            }
            for row in result
        ]


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
