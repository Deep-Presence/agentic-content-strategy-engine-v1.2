"""CPS model architecture classes."""

from .citation_predictor import CitationPredictor
from .feature_selector import (
    OPTION_A_CONFIG,
    OPTION_B_CONFIG,
    SidecarFeatureConfig,
    assemble_sidecar_features,
)
from .fusion_encoder import FusionEncoder

__all__ = [
    "CitationPredictor",
    "FusionEncoder",
    "OPTION_A_CONFIG",
    "OPTION_B_CONFIG",
    "SidecarFeatureConfig",
    "assemble_sidecar_features",
]
