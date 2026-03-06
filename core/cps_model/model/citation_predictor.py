"""Citation Predictor with per-engine heads for CPS.

Architecture (ENG-68):
    Shared Trunk:
        Linear(composite_dim, 256) -> ReLU -> Dropout(0.3)
        Linear(256, 128) -> ReLU -> Dropout(0.2)
        Learns universal citation patterns shared across engines.

    Per-Engine Heads (4 separate nn.Linear):
        Linear(128, composite_dim) -> no activation
        Each head produces a 400d predicted target vector in the same
        embedding space as FusionEncoder output composites.

    Selection Rate Head (shared, content path):
        Linear(composite_dim, 64) -> ReLU -> Linear(64, 1) -> Sigmoid
        Direct CPS regression on content composite (query-independent).
        Serves as both auxiliary training signal and inference CPS score.

    Dense Gated Selection (Codex review):
        All 4 engine heads compute outputs; one-hot multiply+sum selects
        the active head. Eliminates zero-buffer risks from scatter-gather.

Output dimension for predicted_target = composite_dim (same space as
FusionEncoder output for cosine similarity at inference).
"""
from __future__ import annotations

import logging
from typing import NamedTuple

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    nn = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]


if TORCH_AVAILABLE:

    class PredictorOutput(NamedTuple):
        """Output of CitationPredictor.forward().

        Attributes:
            predicted_target: Engine-specific predicted target embeddings
                [B, composite_dim]. Same space as FusionEncoder composites.
            cps_score: Direct CPS prediction from selection rate head
                [B, 1]. Sigmoid-bounded [0, 1].
        """

        predicted_target: torch.Tensor  # [B, composite_dim]
        cps_score: torch.Tensor  # [B, 1]

    class CitationPredictor(nn.Module):
        """Citation prediction with shared trunk and per-engine heads.

        Takes FusionEncoder output composites and produces:
        1. A predicted target embedding (per-engine) for contrastive training.
        2. A direct CPS score (shared) for regression training.

        At inference, CPS = weighted combination of cosine similarity
        (predicted target vs content) and direct regression score.

        Args:
            composite_dim: Input dimension from FusionEncoder (default: 400).
            trunk_hidden: First hidden layer width (default: 256).
            trunk_output: Second hidden / trunk output width (default: 128).
            num_engines: Number of per-engine heads (default: 4).
            trunk_dropout_1: Dropout after first trunk layer (default: 0.3).
            trunk_dropout_2: Dropout after second trunk layer (default: 0.2).
            sr_hidden: Selection rate head hidden width (default: 64).
        """

        def __init__(
            self,
            composite_dim: int = 400,
            trunk_hidden: int = 256,
            trunk_output: int = 128,
            num_engines: int = 4,
            trunk_dropout_1: float = 0.3,
            trunk_dropout_2: float = 0.2,
            sr_hidden: int = 64,
        ) -> None:
            super().__init__()

            # Store dims for external access
            self.composite_dim = composite_dim
            self.trunk_hidden = trunk_hidden
            self.trunk_output = trunk_output
            self.num_engines = num_engines

            # Shared trunk: learns universal citation patterns
            self.trunk = nn.Sequential(
                nn.Linear(composite_dim, trunk_hidden),
                nn.ReLU(),
                nn.Dropout(trunk_dropout_1),
                nn.Linear(trunk_hidden, trunk_output),
                nn.ReLU(),
                nn.Dropout(trunk_dropout_2),
            )

            # Per-engine heads: project trunk output back to composite space
            # No activation — output must be in the same space as FusionEncoder
            # composites for cosine similarity.
            self.engine_heads = nn.ModuleList(
                [nn.Linear(trunk_output, composite_dim) for _ in range(num_engines)]
            )

            # Selection rate head: content composite → CPS score
            # Query-independent by design — it is a content-quality prior.
            # The query-conditioned signal comes from the contrastive path.
            self.selection_rate_head = nn.Sequential(
                nn.Linear(composite_dim, sr_hidden),
                nn.ReLU(),
                nn.Linear(sr_hidden, 1),
                nn.Sigmoid(),
            )

            self._init_weights()

        def _init_weights(self) -> None:
            """Initialize weights with activation-appropriate strategies.

            - Trunk (ReLU): Kaiming normal, fan_out mode.
            - Engine heads (no activation): Kaiming normal.
            - SR head ReLU layer: Kaiming normal.
            - SR head Sigmoid layer: Xavier uniform (prevents saturation).
            """
            # Trunk: all Kaiming for ReLU
            for module in self.trunk.modules():
                if isinstance(module, nn.Linear):
                    nn.init.kaiming_normal_(
                        module.weight, mode="fan_out", nonlinearity="relu"
                    )
                    if module.bias is not None:
                        nn.init.zeros_(module.bias)

            # Engine heads: Kaiming (outputs enter cosine space)
            for head in self.engine_heads:
                nn.init.kaiming_normal_(
                    head.weight, mode="fan_out", nonlinearity="relu"
                )
                if head.bias is not None:
                    nn.init.zeros_(head.bias)

            # Selection rate head: mixed init
            sr_linears = [
                m
                for m in self.selection_rate_head.modules()
                if isinstance(m, nn.Linear)
            ]
            # First Linear (before ReLU): Kaiming
            nn.init.kaiming_normal_(
                sr_linears[0].weight, mode="fan_out", nonlinearity="relu"
            )
            nn.init.zeros_(sr_linears[0].bias)
            # Second Linear (before Sigmoid): Xavier — prevents saturation
            nn.init.xavier_uniform_(sr_linears[1].weight)
            nn.init.zeros_(sr_linears[1].bias)

        def forward(
            self,
            query_composite: torch.Tensor,
            content_composite: torch.Tensor,
            engine_onehot: torch.Tensor,
        ) -> PredictorOutput:
            """Forward pass through trunk + per-engine heads + selection rate head.

            Args:
                query_composite: FusionEncoder output for queries [B, composite_dim].
                content_composite: FusionEncoder output for content [B, composite_dim].
                engine_onehot: One-hot engine encoding [B, num_engines].

            Returns:
                PredictorOutput with predicted_target [B, composite_dim]
                and cps_score [B, 1].
            """
            # Shape validation (debug assertions, no-op with python -O)
            assert (
                query_composite.dim() == 2
                and query_composite.shape[1] == self.composite_dim
            ), (
                f"query_composite shape {query_composite.shape}, "
                f"expected [B, {self.composite_dim}]"
            )
            assert (
                content_composite.dim() == 2
                and content_composite.shape[1] == self.composite_dim
            ), (
                f"content_composite shape {content_composite.shape}, "
                f"expected [B, {self.composite_dim}]"
            )
            assert engine_onehot.dim() == 2, (
                f"engine_onehot must be 2D, got {engine_onehot.dim()}D"
            )
            assert engine_onehot.sum(dim=-1).min() > 0, (
                "engine_onehot contains all-zero row"
            )

            # Shared trunk
            trunk_out = self.trunk(query_composite)  # [B, trunk_output]

            # Dense gated selection: compute all heads, select via one-hot
            all_targets = torch.stack(
                [head(trunk_out) for head in self.engine_heads], dim=1
            )  # [B, num_engines, composite_dim]

            selection = engine_onehot.unsqueeze(-1)  # [B, num_engines, 1]
            predicted_target = (all_targets * selection).sum(
                dim=1
            )  # [B, composite_dim]

            # Selection rate head (operates on CONTENT composite, not query)
            cps_score = self.selection_rate_head(content_composite)  # [B, 1]

            return PredictorOutput(
                predicted_target=predicted_target,
                cps_score=cps_score,
            )

        def predict_target(
            self,
            query_composite: torch.Tensor,
            engine_idx: int,
        ) -> torch.Tensor:
            """Predict ideal target embedding for a single engine.

            Convenience method for inference. All queries go through
            the same engine head — no routing needed.

            Args:
                query_composite: FusionEncoder output [B, composite_dim].
                engine_idx: Which engine head to use (0-3).

            Returns:
                Predicted target [B, composite_dim].

            Raises:
                IndexError: If engine_idx is out of range.
            """
            trunk_out = self.trunk(query_composite)
            return self.engine_heads[engine_idx](trunk_out)

        def predict_cps(
            self,
            query_composite: torch.Tensor,
            content_composite: torch.Tensor,
            engine_idx: int,
            target_weight: float = 0.5,
        ) -> torch.Tensor:
            """Compute final CPS score combining both signals.

            Final CPS = target_weight * cosine_cps + (1 - target_weight) * sr_cps

            where cosine_cps = (cosine_similarity + 1) / 2, mapped to [0, 1].

            Args:
                query_composite: [B_q, composite_dim] — query composites.
                content_composite: [B_c, composite_dim] — content candidates.
                engine_idx: Target engine (0-3).
                target_weight: Weight for contrastive signal vs regression
                    signal (default: 0.5).

            Returns:
                CPS scores [B_c] if B_q == 1, else [B_q, B_c].
            """
            # Contrastive signal
            ideal = self.predict_target(query_composite, engine_idx)  # [B_q, dim]
            ideal_norm = F.normalize(ideal, dim=-1)
            content_norm = F.normalize(content_composite, dim=-1)
            cosine_sim = torch.mm(ideal_norm, content_norm.t())  # [B_q, B_c]
            # Map cosine [-1, 1] to [0, 1]
            cosine_cps = (cosine_sim + 1.0) / 2.0

            # Regression signal
            sr_cps = self.selection_rate_head(content_composite).squeeze(
                -1
            )  # [B_c]

            # Combine signals
            if cosine_cps.shape[0] == 1:
                cosine_cps = cosine_cps.squeeze(0)  # [B_c]

            return target_weight * cosine_cps + (1.0 - target_weight) * sr_cps

else:
    # Stubs for environments without PyTorch (e.g., data collection VM)
    class PredictorOutput:  # type: ignore[no-redef]
        """Stub — PyTorch not available."""

        pass

    class CitationPredictor:  # type: ignore[no-redef]
        """Stub — PyTorch not available."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            raise ImportError("PyTorch is required for CitationPredictor")
