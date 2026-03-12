"""Tests for core.shared_tools.math_utils."""
from __future__ import annotations

import math

import pytest

from core.shared_tools.math_utils import cosine_similarity


class TestCosineSimilarity:
    """Unit tests for cosine_similarity()."""

    def test_identical_vectors(self):
        """Identical unit vectors → similarity 1.0."""
        v = [1.0, 0.0, 0.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        """Orthogonal vectors → similarity 0.0."""
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        """Opposite vectors → similarity -1.0."""
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self):
        """Zero-magnitude vector → 0.0 (no division by zero)."""
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == 0.0

    def test_both_zero_vectors(self):
        """Both zero vectors → 0.0."""
        z = [0.0, 0.0]
        assert cosine_similarity(z, z) == 0.0

    def test_non_unit_vectors(self):
        """Parallel non-unit vectors → similarity 1.0."""
        a = [3.0, 0.0]
        b = [5.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(1.0)

    def test_known_angle(self):
        """45-degree angle → cos(π/4) ≈ 0.7071."""
        a = [1.0, 0.0]
        b = [1.0, 1.0]
        expected = 1.0 / math.sqrt(2.0)
        assert cosine_similarity(a, b) == pytest.approx(expected, rel=1e-6)

    def test_backward_compat_with_agents(self):
        """Verify agents._cosine_similarity delegates to shared impl."""
        from core.topic_discovery.agents import _cosine_similarity

        a = [0.5, 0.3, 0.8]
        b = [0.1, 0.9, 0.4]
        assert _cosine_similarity(a, b) == pytest.approx(cosine_similarity(a, b))
