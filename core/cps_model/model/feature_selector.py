"""Feature selection and assembly for the Sidecar MLP.

Bridges between CPSTrainingDataset's separate feature tensors and
the FusionEncoder's single sidecar input tensor.  Defines which
feature indices from structural[12], citability[9], authority[9],
and domain_cite_rate[1] compose the sidecar input.

Two pre-built configs:
- OPTION_A_CONFIG: 11 features (Phase 2 top-11 subset) — default
- OPTION_B_CONFIG: 31 features (full feature set) — Day 3 ablation
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


# ---------------------------------------------------------------------------
# Feature group sizes (must match feature_assembler.py orderings)
# ---------------------------------------------------------------------------

_STRUCTURAL_DIM = 12
_CITABILITY_DIM = 9
_AUTHORITY_DIM = 9


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SidecarFeatureConfig:
    """Defines which features from each group form the sidecar input.

    Each index tuple refers to positions in the corresponding tensor
    from CPSTrainingDataset.__getitem__().

    Attributes:
        structural_indices: Indices into structural[12] tensor.
        citability_indices: Indices into citability[9] tensor.
        authority_indices: Indices into authority[9] tensor.
        include_domain_cite_rate: Whether to append domain_cite_rate[1].
        name: Human-readable config name for logging.
    """

    structural_indices: Tuple[int, ...]
    citability_indices: Tuple[int, ...]
    authority_indices: Tuple[int, ...]
    include_domain_cite_rate: bool = True
    name: str = "custom"

    @property
    def total_dim(self) -> int:
        """Total number of selected features."""
        n = (
            len(self.structural_indices)
            + len(self.citability_indices)
            + len(self.authority_indices)
        )
        if self.include_domain_cite_rate:
            n += 1
        return n

    def validate(self) -> None:
        """Assert all indices are within valid ranges.

        Raises:
            AssertionError: If any index is out of range for its group.
        """
        for idx in self.structural_indices:
            assert 0 <= idx < _STRUCTURAL_DIM, (
                f"structural index {idx} out of range [0, {_STRUCTURAL_DIM})"
            )
        for idx in self.citability_indices:
            assert 0 <= idx < _CITABILITY_DIM, (
                f"citability index {idx} out of range [0, {_CITABILITY_DIM})"
            )
        for idx in self.authority_indices:
            assert 0 <= idx < _AUTHORITY_DIM, (
                f"authority index {idx} out of range [0, {_AUTHORITY_DIM})"
            )


# ---------------------------------------------------------------------------
# Pre-defined feature configs
# ---------------------------------------------------------------------------

# Option A: Phase 2 top-11 subset (7 structural + 3 citability + 1 domain_cite_rate)
#
# Structural indices (from feature_assembler.STRUCTURAL_FEATURES):
#   2  = has_table_tags
#   5  = header_count
#   6  = paragraph_count
#   7  = bullet_point_count
#   8  = snippet_length_words
#   10 = avg_sentence_length
#   11 = avg_paragraph_length
#
# Citability indices (from feature_assembler.CITABILITY_FEATURES):
#   0 = factual_density
#   3 = self_contained_ratio
#   6 = reading_level
OPTION_A_CONFIG = SidecarFeatureConfig(
    structural_indices=(2, 5, 6, 7, 8, 10, 11),
    citability_indices=(0, 3, 6),
    authority_indices=(),
    include_domain_cite_rate=False,
    name="option_a_top11",
)

# Option B: Full 31-feature set for Day 3 ablation
# All 12 structural + all 9 citability + all 9 authority + 1 domain_cite_rate
OPTION_B_CONFIG = SidecarFeatureConfig(
    structural_indices=tuple(range(_STRUCTURAL_DIM)),
    citability_indices=tuple(range(_CITABILITY_DIM)),
    authority_indices=tuple(range(_AUTHORITY_DIM)),
    include_domain_cite_rate=False,
    name="option_b_full31",
)

# Validate at import time — catches index errors immediately
OPTION_A_CONFIG.validate()
OPTION_B_CONFIG.validate()


# ---------------------------------------------------------------------------
# Feature assembly
# ---------------------------------------------------------------------------


def assemble_sidecar_features(
    batch: Dict[str, Any],
    config: SidecarFeatureConfig,
) -> "torch.Tensor":
    """Select and concatenate features from a dataset batch into a single sidecar tensor.

    Operates on batched tensors (shape [B, ...]) from a DataLoader, not
    single samples.

    Args:
        batch: Dict of tensors from CPSTrainingDataset (batched via DataLoader).
            Expected keys: "structural", "citability", "authority", "domain_cite_rate".
            Shapes: structural [B, 12], citability [B, 9], authority [B, 9],
                    domain_cite_rate [B, 1].
        config: Which feature indices to select from each group.

    Returns:
        Tensor of shape [B, config.total_dim].

    Raises:
        ImportError: If PyTorch is not available.
        ValueError: If config selects zero features.
        KeyError: If required keys are missing from batch.
    """
    if not TORCH_AVAILABLE:
        raise ImportError("PyTorch is required for assemble_sidecar_features")

    parts: List[torch.Tensor] = []

    if config.structural_indices:
        parts.append(batch["structural"][:, list(config.structural_indices)])

    if config.citability_indices:
        parts.append(batch["citability"][:, list(config.citability_indices)])

    if config.authority_indices:
        parts.append(batch["authority"][:, list(config.authority_indices)])

    if config.include_domain_cite_rate:
        parts.append(batch["domain_cite_rate"])  # already [B, 1]

    if not parts:
        raise ValueError("SidecarFeatureConfig selects zero features")

    return torch.cat(parts, dim=-1)
