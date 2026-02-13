from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from core.models.gap_analysis import PlatformResult


class SearchEngine(ABC):
    engine_name: str

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model

    @abstractmethod
    async def search(self, query_text: str, query_id: Optional[str] = None) -> PlatformResult:
        raise NotImplementedError
