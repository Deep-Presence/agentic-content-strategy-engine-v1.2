"""Abstract extractor base class."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict


class BaseExtractor(ABC):
    """Base extractor interface."""

    @abstractmethod
    def extract(self, content: str) -> Dict[str, object]:
        """Extract features from content."""
