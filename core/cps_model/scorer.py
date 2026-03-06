"""CPS Model Scorer — inference wrapper for Content Engine integration.

Loads the trained CPS model and scores content for citation probability.
Supports Markdown content (converted to HTML internally for feature extraction).
Delegates to existing extractors in core/cps_model/extractors/.

Usage:
    scorer = CPSScorer.from_checkpoint(
        checkpoint_path="core/cps_model/best_model.pt",
        scaler_path="core/cps_model/scaler_params.npz",
    )
    result = await scorer.score_async(
        query_texts=["best CRM software"],
        content_markdown="# Best CRM...",
        content_url="https://example.com/crm",
    )
"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from core.config.settings import settings
from core.shared_tools.async_embedding_client import async_embed_texts

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn.functional as F

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import markdown as md

    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

# Markdown extensions for faithful structural conversion
_MD_EXTENSIONS = ["tables", "fenced_code", "nl2br", "sane_lists"]

# Engine ordering (must match training config)
ENGINES = ["chatgpt_search", "claude_search", "gemini_search", "perplexity"]

# Module-level paths (overridable in tests)
_CHECKPOINT_PATH = Path(__file__).parent / "best_model.pt"
_SCALER_PATH = Path(__file__).parent / "scaler_params.npz"


class CPSScorer:
    """Scores content for citation probability using the trained CPS model.

    Delegates feature extraction to existing extractors in core.cps_model.extractors.
    Supports both sync and async scoring.
    """

    ENGINES = ENGINES

    # Feature key ordering — MUST match training index positions.
    _STRUCTURAL_KEYS = [
        "has_ul_tags", "has_ol_tags", "has_table_tags", "has_code_blocks",
        "header_depth", "header_count", "paragraph_count", "bullet_point_count",
        "snippet_length_words", "snippet_length_chars",
        "avg_sentence_length", "avg_paragraph_length",
    ]
    _CITABILITY_KEYS = [
        "factual_density", "specific_claims_count", "data_points_count",
        "self_contained_ratio", "definition_present", "explanation_present",
        "reading_level", "has_key_takeaways", "has_faq_section",
    ]
    _AUTHORITY_KEYS = [
        "domain_authority", "https_status", "is_gov_edu",
        "has_about_page", "has_contact_info", "author_present",
        "has_citations", "has_research_refs", "domain_age_years",
    ]

    def __init__(
        self,
        encoder: Any,
        predictor: Any,
        structural_mean: np.ndarray,
        structural_std: np.ndarray,
        authority_mean: np.ndarray,
        authority_std: np.ndarray,
        citability_mean: np.ndarray,
        citability_std: np.ndarray,
        feature_config_name: str,
        structural_indices: List[int],
        citability_indices: List[int],
        authority_indices: List[int],
        sidecar_input_dim: int,
        device: Any,
        target_weight: float = 0.5,
    ) -> None:
        self.encoder = encoder
        self.predictor = predictor
        self.structural_mean = structural_mean
        self.structural_std = structural_std
        self.authority_mean = authority_mean
        self.authority_std = authority_std
        self.citability_mean = citability_mean
        self.citability_std = citability_std
        self.feature_config_name = feature_config_name
        self.structural_indices = structural_indices
        self.citability_indices = citability_indices
        self.authority_indices = authority_indices
        self.sidecar_input_dim = sidecar_input_dim
        self.device = device
        self.target_weight = target_weight

        # Markdown converter (reusable, stateless per-convert)
        if MARKDOWN_AVAILABLE:
            self._md = md.Markdown(extensions=_MD_EXTENSIONS)

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint_path: str | Path,
        scaler_path: str | Path,
        device: Optional[str] = None,
        target_weight: float = 0.5,
    ) -> "CPSScorer":
        """Load CPS model from a training checkpoint.

        Reads architecture dimensions from the checkpoint config dict,
        NOT from feature_selector.py constants, to handle any dim discrepancy.
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required for CPSScorer")

        # Auto-detect device
        if device:
            dev = torch.device(device)
        elif torch.cuda.is_available():
            dev = torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            dev = torch.device("mps")
        else:
            dev = torch.device("cpu")

        checkpoint = torch.load(
            str(checkpoint_path), map_location=dev, weights_only=False
        )
        config = checkpoint["config"]
        feature_config_name = checkpoint.get("feature_config_name", "option_a")

        # Read encoder config
        enc_cfg = config.get("encoder", {})
        pred_cfg = config.get("predictor", {})

        semantic_dim = enc_cfg.get("semantic_dim", 1536)
        proj_dim = enc_cfg.get("proj_dim", 256)
        sidecar_hidden = enc_cfg.get("sidecar_hidden", 64)
        sidecar_output = enc_cfg.get("sidecar_output", 128)
        num_engines = enc_cfg.get("num_engines", 4)
        engine_embed_dim = enc_cfg.get("engine_embed_dim", 16)
        sidecar_dropout = enc_cfg.get("sidecar_dropout", 0.2)

        # Infer sidecar_input_dim from state dict (authoritative)
        sidecar_weight = checkpoint["encoder_state_dict"].get("sidecar_mlp.0.weight")
        if sidecar_weight is not None:
            sidecar_input_dim = sidecar_weight.shape[1]
        else:
            sidecar_input_dim = 30  # fallback

        # Determine feature indices based on config name and actual dim
        structural_indices, citability_indices, authority_indices = (
            _resolve_feature_indices(feature_config_name, sidecar_input_dim)
        )

        # Build encoder
        from core.cps_model.model.fusion_encoder import FusionEncoder

        encoder = FusionEncoder(
            semantic_dim=semantic_dim,
            proj_dim=proj_dim,
            sidecar_input_dim=sidecar_input_dim,
            sidecar_hidden=sidecar_hidden,
            sidecar_output=sidecar_output,
            num_engines=num_engines,
            engine_embed_dim=engine_embed_dim,
            sidecar_dropout=sidecar_dropout,
        )
        encoder.load_state_dict(checkpoint["encoder_state_dict"])
        encoder.to(dev)
        encoder.eval()

        # Build predictor
        composite_dim = proj_dim + sidecar_output + engine_embed_dim

        from core.cps_model.model.citation_predictor import CitationPredictor

        predictor = CitationPredictor(
            composite_dim=composite_dim,
            trunk_hidden=pred_cfg.get("trunk_hidden", 256),
            trunk_output=pred_cfg.get("trunk_output", 128),
            num_engines=num_engines,
            trunk_dropout_1=pred_cfg.get("trunk_dropout_1", 0.3),
            trunk_dropout_2=pred_cfg.get("trunk_dropout_2", 0.2),
            sr_hidden=pred_cfg.get("sr_hidden", 64),
        )
        predictor.load_state_dict(checkpoint["predictor_state_dict"])
        predictor.to(dev)
        predictor.eval()

        # Load scaler params
        scaler_data = np.load(str(scaler_path))

        return cls(
            encoder=encoder,
            predictor=predictor,
            structural_mean=scaler_data["structural_mean"],
            structural_std=scaler_data["structural_std"],
            authority_mean=scaler_data["authority_mean"],
            authority_std=scaler_data["authority_std"],
            citability_mean=scaler_data["citability_mean"],
            citability_std=scaler_data["citability_std"],
            feature_config_name=feature_config_name,
            structural_indices=structural_indices,
            citability_indices=citability_indices,
            authority_indices=authority_indices,
            sidecar_input_dim=sidecar_input_dim,
            device=dev,
            target_weight=target_weight,
        )

    # ------------------------------------------------------------------
    # Content format handling
    # ------------------------------------------------------------------

    def _normalize_to_html(self, markdown_content: str) -> str:
        """Convert Markdown to HTML for structural feature extraction."""
        self._md.reset()
        return self._md.convert(markdown_content)

    def _get_plain_text(self, markdown_content: str) -> str:
        """Strip Markdown syntax to get clean plain text."""
        text = markdown_content
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"_(.+?)_", r"\1", text)
        text = re.sub(r"`{1,3}[^`]*`{1,3}", "", text)
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"^\s*\|.*\|\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*[-:| ]+\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*>\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n{2,}", "\n", text)
        return text.strip()

    # ------------------------------------------------------------------
    # Feature extraction (delegates to existing extractors)
    # ------------------------------------------------------------------

    def _extract_and_standardize(
        self,
        html: str,
        plain_text: str,
        content_url: str,
    ) -> np.ndarray:
        """Extract features, standardize, assemble sidecar vector."""
        from core.cps_model.extractors.structural import StructuralFeatureExtractor
        from core.cps_model.extractors.citability import CitabilityFeatureExtractor
        from core.cps_model.extractors.authority import AuthorityFeatureExtractor

        # Extract raw features as dicts
        structural_dict = StructuralFeatureExtractor().extract(html)
        citability_dict = CitabilityFeatureExtractor().extract(plain_text)
        authority_dict = AuthorityFeatureExtractor().extract_from_url(
            content_url, html
        )

        # Convert dicts to ordered arrays
        structural = np.array(
            [float(structural_dict[k]) for k in self._STRUCTURAL_KEYS],
            dtype=np.float32,
        )
        citability = np.array(
            [float(citability_dict[k]) for k in self._CITABILITY_KEYS],
            dtype=np.float32,
        )
        authority = np.array(
            [float(authority_dict[k]) for k in self._AUTHORITY_KEYS],
            dtype=np.float32,
        )

        # Standardize (zero std guard: replace 0 with 1 to prevent NaN)
        s_std = np.where(self.structural_std == 0, 1.0, self.structural_std)
        a_std = np.where(self.authority_std == 0, 1.0, self.authority_std)
        c_std = np.where(self.citability_std == 0, 1.0, self.citability_std)

        structural_norm = (structural - self.structural_mean) / s_std
        authority_norm = (authority - self.authority_mean) / a_std
        citability_norm = (citability - self.citability_mean) / c_std

        # Assemble sidecar features (select indices per config)
        parts = []
        if self.structural_indices:
            parts.append(structural_norm[self.structural_indices])
        if self.citability_indices:
            parts.append(citability_norm[self.citability_indices])
        if self.authority_indices:
            parts.append(authority_norm[self.authority_indices])

        sidecar = np.concatenate(parts).astype(np.float32)

        # Pad if checkpoint expects more features (e.g. domain_cite_rate slot)
        if len(sidecar) < self.sidecar_input_dim:
            pad = np.zeros(self.sidecar_input_dim - len(sidecar), dtype=np.float32)
            sidecar = np.concatenate([sidecar, pad])

        return sidecar

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score(
        self,
        query_texts: List[str],
        content_markdown: str,
        content_url: str = "https://example.com",
        query_embeddings: Optional[List[List[float]]] = None,
        content_embedding: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Score content for citation probability (sync).

        When embeddings are not provided, uses the sync embedding client.
        """
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch is required for scoring")

        # Step 1: Normalize content
        html = self._normalize_to_html(content_markdown)
        plain_text = self._get_plain_text(content_markdown)

        # Step 2: Get embeddings (sync fallback)
        if query_embeddings is None or content_embedding is None:
            from core.shared_tools.embedding_client import embed_texts

            all_texts = list(query_texts) + [plain_text[:8000]]
            all_embs = embed_texts(all_texts)
            query_embeddings = all_embs[: len(query_texts)]
            content_embedding = all_embs[-1]

        # Step 3: Extract + standardize features
        sidecar_features = self._extract_and_standardize(
            html, plain_text, content_url
        )

        # Step 4: Run inference
        return self._run_inference(
            query_texts=query_texts,
            query_embeddings=query_embeddings,
            content_embedding=content_embedding,
            sidecar_features=sidecar_features,
        )

    async def score_async(
        self,
        query_texts: List[str],
        content_markdown: str,
        content_url: str = "https://example.com",
        query_embeddings: Optional[List[List[float]]] = None,
        content_embedding: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Score content for citation probability (async).

        Uses async_embed_texts for embeddings. Offloads torch inference
        to a thread via asyncio.to_thread().
        """
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch is required for scoring")

        # Step 1: Normalize content
        html = self._normalize_to_html(content_markdown)
        plain_text = self._get_plain_text(content_markdown)

        # Step 2: Get embeddings (async)
        if query_embeddings is None or content_embedding is None:
            all_texts = list(query_texts) + [plain_text[:8000]]
            all_embs = await async_embed_texts(all_texts)
            query_embeddings = all_embs[: len(query_texts)]
            content_embedding = all_embs[-1]

        # Step 3: Extract + standardize features
        sidecar_features = self._extract_and_standardize(
            html, plain_text, content_url
        )

        # Step 4: Offload torch inference to thread (avoid blocking event loop)
        return await asyncio.to_thread(
            self._run_inference,
            query_texts=query_texts,
            query_embeddings=query_embeddings,
            content_embedding=content_embedding,
            sidecar_features=sidecar_features,
        )

    def _run_inference(
        self,
        query_texts: List[str],
        query_embeddings: List[List[float]],
        content_embedding: List[float],
        sidecar_features: np.ndarray,
    ) -> Dict[str, Any]:
        """Run CPS model inference across all engines and queries."""
        per_query_results: List[Dict[str, Any]] = []

        # Aggregate per-engine scores across all queries
        engine_score_sums = {e: 0.0 for e in self.ENGINES}
        num_queries = len(query_texts)

        with torch.no_grad():
            # Convert content to tensors (shared across queries)
            content_emb_t = torch.tensor(
                content_embedding, dtype=torch.float32
            ).unsqueeze(0).to(self.device)
            sidecar_t = torch.tensor(
                sidecar_features, dtype=torch.float32
            ).unsqueeze(0).to(self.device)

            for q_idx, q_text in enumerate(query_texts):
                query_emb_t = torch.tensor(
                    query_embeddings[q_idx], dtype=torch.float32
                ).unsqueeze(0).to(self.device)

                query_engine_scores: Dict[str, float] = {}
                for engine_idx, engine_name in enumerate(self.ENGINES):
                    engine_onehot = np.zeros(len(self.ENGINES), dtype=np.float32)
                    engine_onehot[engine_idx] = 1.0
                    engine_t = torch.tensor(
                        engine_onehot, dtype=torch.float32
                    ).unsqueeze(0).to(self.device)

                    # Build composites
                    content_composite = self.encoder(
                        embedding=content_emb_t,
                        sidecar_features=sidecar_t,
                        engine_onehot=engine_t,
                        bypass_sidecar=False,
                    )
                    query_composite = self.encoder(
                        embedding=query_emb_t,
                        sidecar_features=sidecar_t,
                        engine_onehot=engine_t,
                        bypass_sidecar=True,
                    )

                    # Get CPS score
                    cps = self.predictor.predict_cps(
                        query_composite=query_composite,
                        content_composite=content_composite,
                        engine_idx=engine_idx,
                        target_weight=self.target_weight,
                    )
                    score_val = round(float(cps.item()), 4)
                    query_engine_scores[engine_name] = score_val
                    engine_score_sums[engine_name] += score_val

                # Per-query average across engines
                q_avg = round(
                    sum(query_engine_scores.values()) / len(query_engine_scores),
                    4,
                )
                per_query_results.append({"query": q_text, "cps_score": q_avg})

        # Average per-engine scores across queries
        per_engine = {
            e: round(engine_score_sums[e] / max(num_queries, 1), 4)
            for e in self.ENGINES
        }

        # Overall CPS = average of per-engine averages
        cps_score = round(
            sum(per_engine.values()) / len(per_engine), 4
        )

        return {
            "cps_score": cps_score,
            "per_engine": per_engine,
            "per_query": per_query_results,
            "model_version": "v1",
            "feature_config": self.feature_config_name,
            "target_weight": self.target_weight,
        }


# ---------------------------------------------------------------------------
# Feature index resolution
# ---------------------------------------------------------------------------


def _resolve_feature_indices(
    config_name: str, sidecar_input_dim: int
) -> tuple:
    """Resolve feature selection indices from config name and actual dim.

    Reads the actual sidecar_input_dim from the checkpoint weight shape
    rather than relying on feature_selector.py constants.
    """
    if config_name in ("option_a", "option_a_top11"):
        structural = [2, 5, 6, 7, 8, 10, 11]
        citability = [0, 3, 6]
        authority: List[int] = []
        # The actual dim may differ from len(structural + citability)
        # if domain_cite_rate was included during training
    elif config_name in ("option_b", "option_b_full31"):
        structural = list(range(12))
        citability = list(range(9))
        authority = list(range(9))
    else:
        # Unknown config — use all features
        structural = list(range(12))
        citability = list(range(9))
        authority = list(range(9))
        logger.warning("Unknown feature config '%s', using full feature set", config_name)

    return structural, citability, authority


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


_scorer_instance: Optional[CPSScorer] = None


def get_cps_scorer() -> Optional[CPSScorer]:
    """Get or create the CPS scorer singleton.

    Returns None if torch is not available, checkpoint not found,
    or CPS scoring is disabled in settings.
    """
    global _scorer_instance
    if _scorer_instance is not None:
        return _scorer_instance

    if not getattr(settings, "cps_enabled", True):
        logger.info("CPS scoring disabled via settings")
        return None

    if not TORCH_AVAILABLE:
        logger.warning("CPS scoring unavailable: torch not installed")
        return None

    if not MARKDOWN_AVAILABLE:
        logger.warning("CPS scoring unavailable: markdown library not installed")
        return None

    if not _CHECKPOINT_PATH.exists() or not _SCALER_PATH.exists():
        logger.warning(
            "CPS scoring unavailable: checkpoint files not found at %s",
            _CHECKPOINT_PATH.parent,
        )
        return None

    try:
        _scorer_instance = CPSScorer.from_checkpoint(
            checkpoint_path=_CHECKPOINT_PATH,
            scaler_path=_SCALER_PATH,
            target_weight=getattr(settings, "cps_target_weight", 0.5),
        )
        logger.info(
            "CPS scorer initialized: config=%s, device=%s",
            _scorer_instance.feature_config_name,
            _scorer_instance.device,
        )
        return _scorer_instance
    except Exception:
        logger.warning("CPS scorer initialization failed", exc_info=True)
        return None
