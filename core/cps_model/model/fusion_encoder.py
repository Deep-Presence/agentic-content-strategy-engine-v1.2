"""Three-stream Fusion Encoder for CPS.

Architecture (ENG-67):
    Stream 1 (Semantic Projection):
        Linear(semantic_dim, proj_dim) -> ReLU -> LayerNorm
        Projects pre-computed frozen embeddings to citation-relevant subspace.

    Stream 2 (Structural Sidecar MLP):
        Linear(sidecar_input, hidden) -> ReLU -> BatchNorm -> Dropout
        Linear(hidden, output) -> ReLU -> BatchNorm
        Learns structural/authority representations from selected features.

    Stream 3 (Engine Conditioning):
        Linear(num_engines, engine_embed_dim) -> ReLU
        Captures per-engine citation preferences.

    Fusion: cat([stream1, stream2, stream3]) -> composite embedding

Output dimension = proj_dim + sidecar_output + engine_embed_dim (default: 400).

Note on BatchNorm: Stream 2 uses BatchNorm1d which requires batch_size > 1
in training mode.  Ensure drop_last=True for the training DataLoader.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    nn = None  # type: ignore[assignment]


if TORCH_AVAILABLE:

    class FusionEncoder(nn.Module):
        """Three-stream encoder producing a composite embedding.

        Streams:
            1. Semantic projection: projects pre-computed embeddings to lower dim.
            2. Structural sidecar MLP: learns format/authority signals.
            3. Engine conditioning: captures per-engine citation preferences.

        Output dimension = proj_dim + sidecar_output + engine_embed_dim.

        Args:
            semantic_dim: Input embedding dimension (default: 1536).
            proj_dim: Semantic projection output dimension (default: 256).
            sidecar_input_dim: Number of sidecar input features (default: 11).
            sidecar_hidden: Sidecar MLP hidden layer width (default: 64).
            sidecar_output: Sidecar MLP output dimension (default: 128).
            num_engines: Number of AI engines (default: 4).
            engine_embed_dim: Engine embedding dimension (default: 16).
            sidecar_dropout: Dropout rate for sidecar MLP (default: 0.2).
        """

        def __init__(
            self,
            semantic_dim: int = 1536,
            proj_dim: int = 256,
            sidecar_input_dim: int = 11,
            sidecar_hidden: int = 64,
            sidecar_output: int = 128,
            num_engines: int = 4,
            engine_embed_dim: int = 16,
            sidecar_dropout: float = 0.2,
        ) -> None:
            super().__init__()

            # Store dims for external access (ENG-68 predictor reads output_dim)
            self.semantic_dim = semantic_dim
            self.proj_dim = proj_dim
            self.sidecar_input_dim = sidecar_input_dim
            self.sidecar_output = sidecar_output
            self.num_engines = num_engines
            self.engine_embed_dim = engine_embed_dim
            self.output_dim = proj_dim + sidecar_output + engine_embed_dim

            # Stream 1: Semantic projection
            # Trainable projection of FROZEN pre-computed embeddings.
            # The OpenAI embeddings are pre-computed and never change;
            # this layer learns WHICH semantic dimensions matter for citation.
            self.semantic_proj = nn.Sequential(
                nn.Linear(semantic_dim, proj_dim),
                nn.ReLU(),
                nn.LayerNorm(proj_dim),
            )

            # Stream 2: Structural sidecar MLP
            # Layer order follows ENG-67 spec: Linear -> ReLU -> BatchNorm
            self.sidecar_mlp = nn.Sequential(
                nn.Linear(sidecar_input_dim, sidecar_hidden),
                nn.ReLU(),
                nn.BatchNorm1d(sidecar_hidden),
                nn.Dropout(sidecar_dropout),
                nn.Linear(sidecar_hidden, sidecar_output),
                nn.ReLU(),
                nn.BatchNorm1d(sidecar_output),
            )

            # Stream 3: Engine conditioning
            self.engine_proj = nn.Sequential(
                nn.Linear(num_engines, engine_embed_dim),
                nn.ReLU(),
            )

            # Learned bias vector for query composites (bypass_sidecar=True).
            # Avoids passing zeros through BatchNorm which corrupts running stats.
            self.query_sidecar_bias = nn.Parameter(
                torch.zeros(sidecar_output)
            )

            # Weight initialization
            self._init_weights()

        def _init_weights(self) -> None:
            """Initialize weights using Kaiming for ReLU activations."""
            for module in self.modules():
                if isinstance(module, nn.Linear):
                    nn.init.kaiming_normal_(
                        module.weight, mode="fan_out", nonlinearity="relu"
                    )
                    if module.bias is not None:
                        nn.init.zeros_(module.bias)
                elif isinstance(module, (nn.BatchNorm1d, nn.LayerNorm)):
                    nn.init.ones_(module.weight)
                    nn.init.zeros_(module.bias)

        def forward(
            self,
            embedding: torch.Tensor,
            sidecar_features: torch.Tensor,
            engine_onehot: torch.Tensor,
            bypass_sidecar: bool = False,
        ) -> torch.Tensor:
            """Forward pass through all three streams with fusion.

            Args:
                embedding: Pre-computed semantic embeddings [B, semantic_dim].
                sidecar_features: Selected structural/citability features
                    [B, sidecar_input_dim]. Ignored when ``bypass_sidecar``
                    is True.
                engine_onehot: Engine one-hot encoding [B, num_engines].
                bypass_sidecar: When True, replace the sidecar MLP output
                    with a learned bias vector (``query_sidecar_bias``).
                    Use this for query composites where no structural
                    features exist.  Avoids passing zeros through BatchNorm
                    which would corrupt running statistics.

            Returns:
                Fused embedding [B, output_dim] where
                output_dim = proj_dim + sidecar_output + engine_embed_dim.
            """
            # Shape validation (debug assertions, no-op with python -O)
            assert embedding.dim() == 2 and embedding.shape[1] == self.semantic_dim, (
                f"embedding shape {embedding.shape}, expected [B, {self.semantic_dim}]"
            )
            assert engine_onehot.dim() == 2, (
                f"engine_onehot must be 2D, got {engine_onehot.dim()}D"
            )

            # Stream 1: Semantic projection (trainable, upstream embeddings frozen)
            sem = self.semantic_proj(embedding)  # [B, proj_dim]

            # Stream 2: Structural sidecar (or learned bias for queries)
            if bypass_sidecar:
                batch_size = embedding.shape[0]
                struct = self.query_sidecar_bias.unsqueeze(0).expand(
                    batch_size, -1
                )  # [B, sidecar_output]
            else:
                assert (
                    sidecar_features.dim() == 2
                    and sidecar_features.shape[1] == self.sidecar_input_dim
                ), (
                    f"sidecar shape {sidecar_features.shape}, "
                    f"expected [B, {self.sidecar_input_dim}]"
                )
                struct = self.sidecar_mlp(sidecar_features)  # [B, sidecar_output]

            # Stream 3: Engine conditioning
            eng = self.engine_proj(engine_onehot)  # [B, engine_embed_dim]

            # Fusion: concatenation
            return torch.cat([sem, struct, eng], dim=-1)  # [B, output_dim]

else:
    # Stub for environments without PyTorch (e.g., data collection VM)
    class FusionEncoder:  # type: ignore[no-redef]
        """Stub — PyTorch not available."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            raise ImportError("PyTorch is required for FusionEncoder")
