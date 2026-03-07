"""Tests that build_graph() functions accept optional checkpointer parameter.

These verify backward compatibility: calling without checkpointer still works,
and passing a MemorySaver produces a compiled graph with checkpointing.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestCompanyGraphCheckpointer:
    def test_compiles_without_checkpointer(self) -> None:
        from core.research.graphs.company_research import build_graph

        graph = build_graph()
        assert graph is not None

    def test_compiles_with_checkpointer(self) -> None:
        from langgraph.checkpoint.memory import MemorySaver
        from core.research.graphs.company_research import build_graph

        checkpointer = MemorySaver()
        graph = build_graph(checkpointer=checkpointer)
        assert graph is not None


class TestStyleGuideGraphCheckpointer:
    def test_compiles_without_checkpointer(self) -> None:
        from core.research.graphs.style_guide import build_graph

        graph = build_graph()
        assert graph is not None

    def test_compiles_with_checkpointer(self) -> None:
        from langgraph.checkpoint.memory import MemorySaver
        from core.research.graphs.style_guide import build_graph

        checkpointer = MemorySaver()
        graph = build_graph(checkpointer=checkpointer)
        assert graph is not None


class TestContentReviewGraphCheckpointer:
    def test_compiles_without_checkpointer(self) -> None:
        from core.content_engine.graph import build_content_review_graph

        graph = build_content_review_graph()
        assert graph is not None

    def test_compiles_with_checkpointer(self) -> None:
        from langgraph.checkpoint.memory import MemorySaver
        from core.content_engine.graph import build_content_review_graph

        checkpointer = MemorySaver()
        graph = build_content_review_graph(checkpointer=checkpointer)
        assert graph is not None
