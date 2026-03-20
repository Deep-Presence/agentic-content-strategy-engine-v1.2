"""Training configuration models.

All hyperparameters for the CPS training pipeline are defined here as
Pydantic models.  No hardcoded values exist in the training loop — every
tuneable parameter lives in this file and is passed via config.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Loss configuration
# ---------------------------------------------------------------------------


class LossConfig(BaseModel):
    """Hyperparameters for CPSLoss (ENG-69).

    Controls the weighted contrastive + regression loss function.
    """

    # Component weights
    alpha: float = 1.0  # contrastive loss weight
    beta: float = 0.3  # regression loss weight

    # Contrastive params
    margin: float = 0.2  # repulsion margin for negative cosine similarity
    margin_warmup_epochs: int = 5  # ramp margin from 0 to target over N epochs

    # Negative tier weights (from pipeline taxonomy)
    hard_negative_weight: float = 2.0
    serp_not_cited_weight: float = 2.0
    serp_cross_platform_weight: float = 1.5
    variable_negative_weight: float = 1.0
    # boundary weight = (1.0 - p_cited_given_retrieved), computed dynamically

    # Triplet mining
    positive_negative_ratio: int = 3  # target negatives per positive
    min_triplets_per_batch: int = 1  # minimum viable triplets; fewer -> regression only
    min_positive_rate: float = 0.3  # minimum selection_rate to qualify as positive

    # Positive weighting (Codex recommendation: tempered to reduce easy-example bias)
    pos_weight_temperature: float = 0.5  # weight = selection_rate ** temp, clipped [0.1, 1.0]

    # Mining strategy (extensible for future semi-hard hybrid)
    mining_strategy: str = "priority"  # "priority" or "semi_hard_hybrid" (future)


# ---------------------------------------------------------------------------
# Optimizer configuration
# ---------------------------------------------------------------------------


class OptimizerConfig(BaseModel):
    """Per-component learning rates and AdamW hyperparameters."""

    semantic_proj_lr: float = 5e-4  # lower LR for projection layer
    sidecar_lr: float = 1e-3  # structural sidecar MLP
    engine_proj_lr: float = 1e-3  # engine conditioning layer
    predictor_lr: float = 1e-3  # shared trunk + per-engine heads + SR head
    weight_decay: float = 0.01


# ---------------------------------------------------------------------------
# Scheduler configuration
# ---------------------------------------------------------------------------


class SchedulerConfig(BaseModel):
    """CosineAnnealingLR parameters."""

    T_max: int = 100
    eta_min: float = 1e-5


# ---------------------------------------------------------------------------
# Early stopping configuration
# ---------------------------------------------------------------------------


class EarlyStoppingConfig(BaseModel):
    """Early stopping on validation loss."""

    patience: int = 10
    min_delta: float = 0.0  # minimum improvement to count as better


# ---------------------------------------------------------------------------
# Model architecture configurations
# ---------------------------------------------------------------------------


class EncoderConfig(BaseModel):
    """FusionEncoder architecture dimensions (ENG-67)."""

    semantic_dim: int = 1536  # input embedding dim (text-embedding-3-small)
    proj_dim: int = 256  # semantic projection output dim
    sidecar_hidden: int = 64  # sidecar MLP hidden layer width
    sidecar_output: int = 128  # sidecar MLP output dim
    num_engines: int = 4  # number of AI engines
    engine_embed_dim: int = 16  # engine conditioning output dim
    sidecar_dropout: float = 0.2  # dropout rate in sidecar MLP


class PredictorConfig(BaseModel):
    """CitationPredictor architecture dimensions (ENG-68)."""

    trunk_hidden: int = 256  # first hidden layer width
    trunk_output: int = 128  # second hidden / trunk output width
    trunk_dropout_1: float = 0.3  # dropout after first trunk layer
    trunk_dropout_2: float = 0.2  # dropout after second trunk layer
    sr_hidden: int = 64  # selection rate head hidden width


# ---------------------------------------------------------------------------
# Experiment tracking configuration
# ---------------------------------------------------------------------------


class WandbConfig(BaseModel):
    """Weights & Biases experiment tracking configuration."""

    project: str = "cps-training"
    entity: Optional[str] = None  # None = personal workspace
    run_name: Optional[str] = None  # None = auto-generated
    tags: List[str] = Field(default_factory=list)
    enabled: bool = True
    watch_models: bool = False  # wandb.watch() for gradient histograms
    log_freq: int = 1  # log every N batches (1 = every batch)


# ---------------------------------------------------------------------------
# Checkpoint configuration
# ---------------------------------------------------------------------------


class CheckpointConfig(BaseModel):
    """Model checkpointing configuration."""

    dir: str = "data/training/checkpoints"
    save_top_k: int = 1  # number of best checkpoints to keep
    resume_from: Optional[str] = None  # path to checkpoint to resume from


# ---------------------------------------------------------------------------
# Top-level training configuration
# ---------------------------------------------------------------------------


class TrainingConfig(BaseModel):
    """Unified configuration for CPS training pipeline.

    Includes data preparation, model architecture, optimizer, scheduler,
    loss function, experiment tracking, and checkpointing.  All values have
    defaults for backward compatibility — ``TrainingConfig(sqlite_path=...,
    chroma_path=...)`` still works for ``training-prepare``.
    """

    # Database paths
    sqlite_path: str
    database_url: Optional[str] = None  # pgvector-backed storage (preferred)

    # ChromaDB paths — DEPRECATED (retained for backward compat with external training repo)
    chroma_path: Optional[str] = None
    chroma_snippet_collection: Optional[str] = "snippet_embeddings"
    chroma_query_collection: Optional[str] = "query_embeddings"

    # Feature dimensions (derived from Pydantic models in schemas/models.py)
    embedding_dim: int = 1536  # text-embedding-3-small

    # Engine list (for one-hot encoding) — order matters for reproducibility
    engines: List[str] = Field(
        default_factory=lambda: [
            "chatgpt_search",
            "claude_search",
            "gemini_search",
            "perplexity",
        ]
    )

    # Split ratios
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15

    # DataLoader settings
    batch_size: int = 256
    num_workers: int = 4

    # Output paths
    output_dir: str = "data/training"

    # Domain cite rate smoothing prior (Bayesian target encoding)
    domain_prior_count: int = 10

    # Random seed for reproducibility
    seed: int = 42

    # --- Training loop ---
    max_epochs: int = 100
    gradient_clip_max_norm: float = 1.0

    # Feature config selection: "option_a" (11 features) or "option_b" (31 features)
    feature_config: str = "option_b"

    # Baseline comparison
    frequency_baseline_f1: float = 0.762

    # Metrics thresholds
    citation_threshold: float = 0.0  # selection_rate > this = cited
    prediction_threshold: float = 0.3  # CPS score > this = predicted cited

    # --- Nested configs ---
    loss: LossConfig = Field(default_factory=LossConfig)
    optimizer: OptimizerConfig = Field(default_factory=OptimizerConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    early_stopping: EarlyStoppingConfig = Field(default_factory=EarlyStoppingConfig)
    encoder: EncoderConfig = Field(default_factory=EncoderConfig)
    predictor: PredictorConfig = Field(default_factory=PredictorConfig)
    wandb: WandbConfig = Field(default_factory=WandbConfig)
    checkpoint: CheckpointConfig = Field(default_factory=CheckpointConfig)
