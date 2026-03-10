# CPS Model Integration Guide

> **Purpose:** This document provides everything needed to integrate the Citation Signal Predictor (CPS) model into a product platform. It is written for an AI coding assistant (or engineer) working on a separate codebase that needs to consume this model as a scoring service.

---

## 1. What the CPS Model Does

The CPS model predicts **how likely a piece of content is to be cited by AI answer engines** (ChatGPT, Perplexity, Claude, Gemini) for a given query. It produces a **Citation Probability Score (CPS)** between 0.0 and 1.0.

**Use case in your product:** Your content engine agent produces an article/blog for a given query. You pass the query + content to the CPS model, and it returns a citability score indicating how likely AI engines are to cite that content when answering that query.

### What the Score Means

| CPS Score | Interpretation |
|-----------|----------------|
| 0.0 - 0.2 | Very unlikely to be cited |
| 0.2 - 0.4 | Low citation probability |
| 0.4 - 0.6 | Moderate citation probability |
| 0.6 - 0.8 | High citation probability |
| 0.8 - 1.0 | Very high citation probability |

The score combines two signals:
1. **Contrastive signal** — How close the content embedding is to what the model predicts an AI engine would ideally cite for this query (cosine similarity in a learned embedding space).
2. **Regression signal** — A direct quality-of-content score from a dedicated selection rate head (query-independent content prior).

---

## 2. Model Architecture Overview

The CPS model has two main components:

### 2.1 FusionEncoder (Three-Stream Encoder)

Produces a composite embedding by fusing three information streams:

```
Stream 1: Semantic Projection
  Linear(1536, 256) -> ReLU -> LayerNorm
  Projects pre-computed OpenAI embeddings into a citation-relevant subspace.

Stream 2: Structural Sidecar MLP
  Linear(N, 64) -> ReLU -> BatchNorm -> Dropout(0.2) -> Linear(64, 128) -> ReLU -> BatchNorm
  Learns structural/authority/citability feature representations.
  N = 11 (option_a) or 30 (option_b) depending on feature config.

Stream 3: Engine Conditioning
  Linear(4, 16) -> ReLU
  Captures per-engine citation preferences via one-hot encoding.

Fusion: concatenate([stream1, stream2, stream3])
Output dimension: 256 + 128 + 16 = 400
```

The encoder processes both **query composites** (semantic embedding + engine, with sidecar bypassed) and **content composites** (semantic embedding + structural features + engine).

### 2.2 CitationPredictor (Per-Engine Prediction Heads)

Takes encoder composites and produces the CPS score:

```
Shared Trunk:
  Linear(400, 256) -> ReLU -> Dropout(0.3) -> Linear(256, 128) -> ReLU -> Dropout(0.2)

Per-Engine Heads (4 heads, one per AI engine):
  Linear(128, 400) -> no activation
  Predicts the "ideal cited content" embedding for each engine.

Selection Rate Head (shared):
  Linear(400, 64) -> ReLU -> Linear(64, 1) -> Sigmoid
  Direct CPS regression score [0, 1].
```

### 2.3 Inference Flow

```
Final CPS = target_weight * cosine_cps + (1 - target_weight) * sr_cps

where:
  cosine_cps = (cosine_similarity(predicted_ideal, content_composite) + 1) / 2
  sr_cps = selection_rate_head(content_composite)
  target_weight = 0.5 (default, tunable)
```

---

## 3. Inputs Required

To score a piece of content for a given query, the model needs:

### 3.1 Query Embedding (1536-dim float vector)

- **Model:** OpenAI `text-embedding-3-small`
- **How to get it:** Call the OpenAI embeddings API with the query text.

```python
from openai import OpenAI

client = OpenAI(api_key="YOUR_OPENAI_API_KEY")
response = client.embeddings.create(
    model="text-embedding-3-small",
    input="best project management tools for remote teams"
)
query_embedding = response.data[0].embedding  # List[float], len=1536
```

### 3.2 Content Embedding (1536-dim float vector)

- **Model:** OpenAI `text-embedding-3-small` (same model as query)
- **How to get it:** Embed the content text (or a representative snippet — first ~8000 chars recommended for token limits).

```python
response = client.embeddings.create(
    model="text-embedding-3-small",
    input=content_text[:8000]
)
content_embedding = response.data[0].embedding  # List[float], len=1536
```

### 3.3 Content Format: HTML or Markdown

The feature extractors need to detect structural elements (headers, lists, tables, code blocks, etc.) from the content. The CPS model was trained on HTML-sourced features, but your content engine may produce **Markdown** instead.

**Both formats are supported.** The integration wrapper accepts a `content_format` parameter:
- `"html"` — Features extracted directly from HTML tags.
- `"markdown"` — Markdown is first converted to HTML (via the `markdown` library with `tables`, `fenced_code`, `nl2br` extensions), then the same HTML extractors run on the converted output. This ensures feature parity between formats.

The Markdown conversion preserves all structural signals: `#`/`##` headers become `<h1>`/`<h2>`, `-`/`*` lists become `<ul><li>`, `|` tables become `<table>`, fenced code blocks become `<pre><code>`, etc.

### 3.4 Structural Features (12 floats)

Extracted from content (HTML or Markdown-converted-to-HTML). These measure document structure:

| Index | Feature | Type | Description |
|-------|---------|------|-------------|
| 0 | `has_ul_tags` | bool (0/1) | Has unordered lists |
| 1 | `has_ol_tags` | bool (0/1) | Has ordered lists |
| 2 | `has_table_tags` | bool (0/1) | Has HTML tables |
| 3 | `has_code_blocks` | bool (0/1) | Has `<code>` or `<pre>` blocks |
| 4 | `header_depth` | int | Max header level depth (1-6, or 0) |
| 5 | `header_count` | int | Number of headers |
| 6 | `paragraph_count` | int | Number of `<p>` tags |
| 7 | `bullet_point_count` | int | Number of `<li>` items |
| 8 | `snippet_length_words` | int | Word count |
| 9 | `snippet_length_chars` | int | Character count |
| 10 | `avg_sentence_length` | float | Average words per sentence |
| 11 | `avg_paragraph_length` | float | Average words per paragraph |

### 3.5 Authority Features (9 floats)

Extracted from the content URL and HTML. These measure source credibility:

| Index | Feature | Type | Description |
|-------|---------|------|-------------|
| 0 | `domain_authority` | float | 10.0 for .gov/.edu, 1.0 otherwise |
| 1 | `https_status` | bool (0/1) | Uses HTTPS |
| 2 | `is_gov_edu` | bool (0/1) | Is a .gov or .edu domain |
| 3 | `has_about_page` | bool (0/1) | Links to an "about" page |
| 4 | `has_contact_info` | bool (0/1) | Links to "contact" page |
| 5 | `author_present` | bool (0/1) | Author attribution detected |
| 6 | `has_citations` | bool (0/1) | Contains DOIs or `[N]` references |
| 7 | `has_research_refs` | bool (0/1) | References arxiv/pubmed/doi.org |
| 8 | `domain_age_years` | float | Domain age (0.0 if unknown) |

### 3.6 Citability Features (9 floats)

Extracted from the content text (plain text, format-independent). These measure how "citable" the content is:

| Index | Feature | Type | Description |
|-------|---------|------|-------------|
| 0 | `factual_density` | float | % of tokens containing digits |
| 1 | `specific_claims_count` | int | Sentences with assertive verbs |
| 2 | `data_points_count` | int | Count of numeric tokens |
| 3 | `self_contained_ratio` | float | Ratio of sentences >= 8 words |
| 4 | `definition_present` | bool (0/1) | Contains "X is Y" patterns |
| 5 | `explanation_present` | bool (0/1) | Contains causal connectors |
| 6 | `reading_level` | float | Flesch-Kincaid grade level |
| 7 | `has_key_takeaways` | bool (0/1) | Has "key takeaways" / "summary" |
| 8 | `has_faq_section` | bool (0/1) | Has FAQ section |

### 3.7 Engine Selection (one-hot, 4 floats)

Which AI engine you're targeting. Order matters:

| Index | Engine |
|-------|--------|
| 0 | `chatgpt_search` |
| 1 | `claude_search` |
| 2 | `gemini_search` |
| 3 | `perplexity` |

To score across all engines, run inference 4 times (once per engine) or average the scores.

---

## 4. Outputs

### 4.1 CPS Score (Primary Output)

A single float in `[0.0, 1.0]` representing citation probability.

### 4.2 Per-Engine Scores (Optional)

Run inference with each engine one-hot to get engine-specific scores:
- `cps_chatgpt` — Citation probability for ChatGPT Search
- `cps_claude` — Citation probability for Claude Search
- `cps_gemini` — Citation probability for Gemini Search
- `cps_perplexity` — Citation probability for Perplexity

### 4.3 Suggested Response Schema

```json
{
  "query": "best project management tools for remote teams",
  "content_url": "https://example.com/article",
  "cps_score": 0.72,
  "per_engine_scores": {
    "chatgpt_search": 0.75,
    "claude_search": 0.68,
    "gemini_search": 0.71,
    "perplexity": 0.74
  },
  "model_version": "v1",
  "feature_config": "option_b"
}
```

---

## 5. Artifacts Required

The following files from the CPS model repository are needed for inference:

### 5.1 Model Checkpoint

```
cps_model/data/training/checkpoints/best_model.pt
```

This is a PyTorch checkpoint containing:
- `encoder_state_dict` — FusionEncoder weights
- `predictor_state_dict` — CitationPredictor weights
- `config` — Full TrainingConfig as a dict (includes all architecture dimensions)
- `feature_config_name` — Which feature config was used ("option_a" or "option_b")

### 5.2 Scaler Parameters

```
cps_model/data/training/scaler_params.npz
```

Contains standardization parameters (mean/std) for the three feature groups, computed from the training set. **You must apply these to normalize features before inference.**

Contents:
- `structural_mean` (12,), `structural_std` (12,)
- `authority_mean` (9,), `authority_std` (9,)
- `citability_mean` (9,), `citability_std` (9,)

### 5.3 Model Source Code (Minimal)

You need the model class definitions to load the checkpoint. The minimum files to copy or package:

```
cps_pipeline/training/model/fusion_encoder.py    # FusionEncoder class
cps_pipeline/training/model/citation_predictor.py # CitationPredictor class
cps_pipeline/training/model/feature_selector.py   # SidecarFeatureConfig, OPTION_A/B_CONFIG
cps_pipeline/training/model/__init__.py           # Exports
cps_pipeline/training/config.py                    # TrainingConfig (for checkpoint loading)
cps_pipeline/training/dataset.py                   # load_scaler_params()
```

### 5.4 Feature Extractors (Optional but Recommended)

If you want to extract features from raw HTML content (rather than computing them yourself):

```
cps_pipeline/extractors/base.py
cps_pipeline/extractors/structural.py     # StructuralFeatureExtractor
cps_pipeline/extractors/authority.py      # AuthorityFeatureExtractor
cps_pipeline/extractors/citability.py     # CitabilityFeatureExtractor
```

---

## 6. Dependencies

### 6.1 Required Python Packages for Inference

```
torch>=2.2.0
numpy>=1.26.0
pydantic>=2.6.0
openai>=1.30.0           # For embedding generation
beautifulsoup4>=4.12.0   # For feature extraction from HTML
markdown>=3.5.0          # For Markdown -> HTML conversion (if content is Markdown)
```

### 6.2 Optional (Not Needed for Inference)

These are training/pipeline dependencies — **not needed** for inference:
- `wandb`, `scikit-learn`, `chromadb`, `sqlalchemy`, `aiosqlite`
- `playwright`, `httpx`, `typer`, `pandas`, `pyarrow`

### 6.3 Hardware

- **CPU inference is fine** — the model is small (~600K parameters total).
- GPU/MPS acceleration available if torch detects it.
- Memory: < 50MB for model weights + embeddings.

---

## 7. Integration Guide: Step by Step

### Step 1: Copy Artifacts

Copy these files from the CPS model repo into your project:

```bash
# Create a directory for the CPS model in your product
mkdir -p your_project/cps_model/

# Copy the checkpoint and scaler
cp cps_model/data/training/checkpoints/best_model.pt your_project/cps_model/
cp cps_model/data/training/scaler_params.npz your_project/cps_model/

# Copy the minimal model source code
mkdir -p your_project/cps_model/model/
cp cps_model/cps_pipeline/training/model/fusion_encoder.py your_project/cps_model/model/
cp cps_model/cps_pipeline/training/model/citation_predictor.py your_project/cps_model/model/
cp cps_model/cps_pipeline/training/model/feature_selector.py your_project/cps_model/model/
cp cps_model/cps_pipeline/training/config.py your_project/cps_model/

# Copy feature extractors
mkdir -p your_project/cps_model/extractors/
cp cps_model/cps_pipeline/extractors/base.py your_project/cps_model/extractors/
cp cps_model/cps_pipeline/extractors/structural.py your_project/cps_model/extractors/
cp cps_model/cps_pipeline/extractors/authority.py your_project/cps_model/extractors/
cp cps_model/cps_pipeline/extractors/citability.py your_project/cps_model/extractors/
```

> **Important:** You will need to adjust the import paths in the copied files to match your project structure. The original code uses `cps_pipeline.training.model.*` and `cps_pipeline.extractors.*` imports.

### Step 2: Install Dependencies

```bash
pip install torch numpy pydantic openai beautifulsoup4 markdown
```

### Step 3: Write the Inference Wrapper

Below is a complete, self-contained inference class you can adapt:

```python
"""CPS Model Inference Wrapper.

Loads the trained CPS model and scores content for citation probability.
Supports both HTML and Markdown content formats.
"""
from __future__ import annotations

import re
from typing import Dict, List, Literal, Optional
from urllib.parse import urlparse

import markdown as md
import numpy as np
import torch
import torch.nn.functional as F
from bs4 import BeautifulSoup
from openai import OpenAI

# Markdown extensions for faithful structural conversion
_MD_EXTENSIONS = ["tables", "fenced_code", "nl2br", "sane_lists"]


class CPSScorer:
    """Scores content for citation probability using the trained CPS model.

    Supports both HTML and Markdown content. Markdown is converted to HTML
    internally so that the same structural feature extractors work for both.

    Usage (HTML):
        scorer = CPSScorer(
            checkpoint_path="cps_model/best_model.pt",
            scaler_path="cps_model/scaler_params.npz",
            openai_api_key="sk-...",
        )
        result = scorer.score(
            query="best project management tools",
            content="<h1>Top PM Tools</h1><p>Here are the best...</p>",
            content_format="html",
            content_url="https://example.com/pm-tools",
        )

    Usage (Markdown — typical for content engine output):
        result = scorer.score(
            query="best project management tools",
            content="# Top PM Tools\\n\\nHere are the best...\\n\\n- Tool A\\n- Tool B",
            content_format="markdown",
            content_url="https://example.com/pm-tools",
        )
    """

    ENGINES = ["chatgpt_search", "claude_search", "gemini_search", "perplexity"]
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIM = 1536

    def __init__(
        self,
        checkpoint_path: str,
        scaler_path: str,
        openai_api_key: str,
        device: Optional[str] = None,
        target_weight: float = 0.5,
    ) -> None:
        """Initialize the CPS scorer.

        Args:
            checkpoint_path: Path to best_model.pt checkpoint.
            scaler_path: Path to scaler_params.npz.
            openai_api_key: OpenAI API key for embeddings.
            device: Torch device ("cpu", "cuda", "mps"). Auto-detected if None.
            target_weight: Weight for contrastive vs regression signal (0-1).
                Higher = more weight on query-content relevance.
                Lower = more weight on content quality prior.
        """
        self.target_weight = target_weight
        self.openai_client = OpenAI(api_key=openai_api_key)

        # Markdown converter (reusable, stateless per-convert)
        self._md = md.Markdown(extensions=_MD_EXTENSIONS)

        # Auto-detect device
        if device:
            self.device = torch.device(device)
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = torch.device("mps")
        else:
            self.device = torch.device("cpu")

        # Load checkpoint
        checkpoint = torch.load(
            checkpoint_path, map_location=self.device, weights_only=False
        )
        config = checkpoint["config"]
        feature_config_name = checkpoint.get("feature_config_name", "option_a")

        # Determine feature config
        self.feature_config_name = feature_config_name
        self._setup_feature_config(feature_config_name)

        # Build models from checkpoint config
        enc_cfg = config.get("encoder", {})
        pred_cfg = config.get("predictor", {})

        semantic_dim = enc_cfg.get("semantic_dim", 1536)
        proj_dim = enc_cfg.get("proj_dim", 256)
        sidecar_hidden = enc_cfg.get("sidecar_hidden", 64)
        sidecar_output = enc_cfg.get("sidecar_output", 128)
        num_engines = enc_cfg.get("num_engines", 4)
        engine_embed_dim = enc_cfg.get("engine_embed_dim", 16)
        sidecar_dropout = enc_cfg.get("sidecar_dropout", 0.2)

        # Import model classes (adjust these imports to your project structure)
        from cps_model.model.fusion_encoder import FusionEncoder
        from cps_model.model.citation_predictor import CitationPredictor

        self.encoder = FusionEncoder(
            semantic_dim=semantic_dim,
            proj_dim=proj_dim,
            sidecar_input_dim=self.sidecar_input_dim,
            sidecar_hidden=sidecar_hidden,
            sidecar_output=sidecar_output,
            num_engines=num_engines,
            engine_embed_dim=engine_embed_dim,
            sidecar_dropout=sidecar_dropout,
        )
        self.encoder.load_state_dict(checkpoint["encoder_state_dict"])
        self.encoder.to(self.device)
        self.encoder.eval()

        composite_dim = proj_dim + sidecar_output + engine_embed_dim

        self.predictor = CitationPredictor(
            composite_dim=composite_dim,
            trunk_hidden=pred_cfg.get("trunk_hidden", 256),
            trunk_output=pred_cfg.get("trunk_output", 128),
            num_engines=num_engines,
            trunk_dropout_1=pred_cfg.get("trunk_dropout_1", 0.3),
            trunk_dropout_2=pred_cfg.get("trunk_dropout_2", 0.2),
            sr_hidden=pred_cfg.get("sr_hidden", 64),
        )
        self.predictor.load_state_dict(checkpoint["predictor_state_dict"])
        self.predictor.to(self.device)
        self.predictor.eval()

        # Load scaler parameters
        scaler_data = np.load(scaler_path)
        self.structural_mean = scaler_data["structural_mean"]
        self.structural_std = scaler_data["structural_std"]
        self.authority_mean = scaler_data["authority_mean"]
        self.authority_std = scaler_data["authority_std"]
        self.citability_mean = scaler_data["citability_mean"]
        self.citability_std = scaler_data["citability_std"]

    def _setup_feature_config(self, name: str) -> None:
        """Setup feature selection indices based on config name."""
        if name == "option_a" or name == "option_a_top11":
            # 11 features: 7 structural + 3 citability
            self.structural_indices = [2, 5, 6, 7, 8, 10, 11]
            self.citability_indices = [0, 3, 6]
            self.authority_indices = []
            self.include_domain_cite_rate = False
            self.sidecar_input_dim = 11
        else:
            # option_b: all 30 features (12 structural + 9 citability + 9 authority)
            self.structural_indices = list(range(12))
            self.citability_indices = list(range(9))
            self.authority_indices = list(range(9))
            self.include_domain_cite_rate = False
            self.sidecar_input_dim = 30

    # ------------------------------------------------------------------
    # Content format handling
    # ------------------------------------------------------------------

    def _normalize_to_html(
        self,
        content: str,
        content_format: Literal["html", "markdown"],
    ) -> str:
        """Convert content to HTML if needed.

        Markdown is converted using the Python `markdown` library with
        extensions for tables, fenced code blocks, line breaks, and
        sane list handling. This produces the same HTML tags (h1-h6,
        ul, ol, li, table, pre, code, p) that the feature extractors
        rely on.

        Args:
            content: Raw content string.
            content_format: "html" or "markdown".

        Returns:
            HTML string ready for feature extraction.
        """
        if content_format == "html":
            return content

        # Reset the converter's internal state (required for reuse)
        self._md.reset()
        return self._md.convert(content)

    def _get_plain_text(
        self,
        content: str,
        content_format: Literal["html", "markdown"],
    ) -> str:
        """Extract plain text for embedding and citability features.

        For Markdown, strips syntax directly (avoids double-conversion
        artifacts). For HTML, uses BeautifulSoup.

        Args:
            content: Raw content string.
            content_format: "html" or "markdown".

        Returns:
            Clean plain text.
        """
        if content_format == "html":
            return BeautifulSoup(content, "html.parser").get_text(" ", strip=True)

        # Strip common Markdown syntax for clean text
        text = content
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # headers
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # bold
        text = re.sub(r"\*(.+?)\*", r"\1", text)  # italic
        text = re.sub(r"__(.+?)__", r"\1", text)  # bold alt
        text = re.sub(r"_(.+?)_", r"\1", text)  # italic alt
        text = re.sub(r"`{1,3}[^`]*`{1,3}", "", text)  # inline/fenced code
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)  # unordered list markers
        text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)  # ordered list markers
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # links
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)  # images
        text = re.sub(r"^\s*\|.*\|\s*$", "", text, flags=re.MULTILINE)  # table rows
        text = re.sub(r"^\s*[-:| ]+\s*$", "", text, flags=re.MULTILINE)  # table separators
        text = re.sub(r"^\s*>\s+", "", text, flags=re.MULTILINE)  # blockquotes
        text = re.sub(r"\n{2,}", "\n", text)  # collapse blank lines
        return text.strip()

    # ------------------------------------------------------------------
    # Main scoring API
    # ------------------------------------------------------------------

    def score(
        self,
        query: str,
        content: str,
        content_format: Literal["html", "markdown"] = "markdown",
        content_url: str = "https://example.com",
        engines: Optional[List[str]] = None,
    ) -> Dict:
        """Score content for citation probability.

        Args:
            query: The search query.
            content: The content as HTML or Markdown string.
            content_format: "html" or "markdown" (default: "markdown").
            content_url: The URL where the content would be published.
            engines: Which engines to score for. Default: all 4.

        Returns:
            Dict with "cps_score" (average across engines) and
            "per_engine" (dict of engine -> score).
        """
        engines = engines or self.ENGINES

        # Step 1: Normalize content
        html = self._normalize_to_html(content, content_format)
        plain_text = self._get_plain_text(content, content_format)

        # Step 2: Get embeddings from OpenAI
        query_embedding = self._get_embedding(query)
        content_embedding = self._get_embedding(plain_text[:8000])

        # Step 3: Extract features (always from HTML — Markdown was converted)
        structural = self._extract_structural(html)
        authority = self._extract_authority(content_url, html)
        citability = self._extract_citability(plain_text)

        # Step 4: Standardize features
        structural_norm = (structural - self.structural_mean) / self.structural_std
        authority_norm = (authority - self.authority_mean) / self.authority_std
        citability_norm = (citability - self.citability_mean) / self.citability_std

        # Step 5: Assemble sidecar features (select indices per config)
        sidecar_parts = []
        if self.structural_indices:
            sidecar_parts.append(structural_norm[self.structural_indices])
        if self.citability_indices:
            sidecar_parts.append(citability_norm[self.citability_indices])
        if self.authority_indices:
            sidecar_parts.append(authority_norm[self.authority_indices])
        sidecar_features = np.concatenate(sidecar_parts).astype(np.float32)

        # Step 6: Run inference for each engine
        per_engine_scores = {}
        with torch.no_grad():
            for engine in engines:
                engine_idx = self.ENGINES.index(engine)
                engine_onehot = np.zeros(len(self.ENGINES), dtype=np.float32)
                engine_onehot[engine_idx] = 1.0

                # Convert to tensors [1, dim] (batch size = 1)
                query_emb_t = torch.tensor(query_embedding, dtype=torch.float32).unsqueeze(0).to(self.device)
                content_emb_t = torch.tensor(content_embedding, dtype=torch.float32).unsqueeze(0).to(self.device)
                sidecar_t = torch.tensor(sidecar_features, dtype=torch.float32).unsqueeze(0).to(self.device)
                engine_t = torch.tensor(engine_onehot, dtype=torch.float32).unsqueeze(0).to(self.device)

                # Build content composite (with sidecar features)
                content_composite = self.encoder(
                    embedding=content_emb_t,
                    sidecar_features=sidecar_t,
                    engine_onehot=engine_t,
                    bypass_sidecar=False,
                )

                # Build query composite (bypass sidecar — queries have no structural features)
                query_composite = self.encoder(
                    embedding=query_emb_t,
                    sidecar_features=sidecar_t,  # ignored when bypass=True
                    engine_onehot=engine_t,
                    bypass_sidecar=True,
                )

                # Get CPS score via predict_cps
                cps = self.predictor.predict_cps(
                    query_composite=query_composite,
                    content_composite=content_composite,
                    engine_idx=engine_idx,
                    target_weight=self.target_weight,
                )

                per_engine_scores[engine] = round(float(cps.item()), 4)

        # Average across engines
        avg_score = round(
            sum(per_engine_scores.values()) / len(per_engine_scores), 4
        )

        return {
            "cps_score": avg_score,
            "per_engine": per_engine_scores,
            "content_format": content_format,
            "model_version": "v1",
            "feature_config": self.feature_config_name,
        }

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding from OpenAI API."""
        response = self.openai_client.embeddings.create(
            model=self.EMBEDDING_MODEL,
            input=text,
        )
        return np.array(response.data[0].embedding, dtype=np.float32)

    # ------------------------------------------------------------------
    # Feature extractors (operate on HTML — Markdown is pre-converted)
    # ------------------------------------------------------------------

    def _extract_structural(self, html: str) -> np.ndarray:
        """Extract 12 structural features from HTML."""
        soup = BeautifulSoup(html or "", "html.parser")
        text = soup.get_text(" ", strip=True)
        words = text.split()

        headers = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        header_levels = [int(h.name[1]) for h in headers if h.name and h.name[1].isdigit()]
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        para_word_counts = [len(p.split()) for p in paragraphs if p]
        sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
        sent_lengths = [len(s.split()) for s in sentences if s.strip()]

        return np.array([
            1.0 if soup.find_all("ul") else 0.0,        # has_ul_tags
            1.0 if soup.find_all("ol") else 0.0,        # has_ol_tags
            1.0 if soup.find_all("table") else 0.0,     # has_table_tags
            1.0 if soup.find_all(["code", "pre"]) else 0.0,  # has_code_blocks
            float(max(header_levels) if header_levels else 0),  # header_depth
            float(len(headers)),                          # header_count
            float(len(paragraphs)),                       # paragraph_count
            float(len(soup.find_all("li"))),             # bullet_point_count
            float(len(words)),                            # snippet_length_words
            float(len(text)),                             # snippet_length_chars
            sum(sent_lengths) / len(sent_lengths) if sent_lengths else 0.0,  # avg_sentence_length
            sum(para_word_counts) / len(para_word_counts) if para_word_counts else 0.0,  # avg_paragraph_length
        ], dtype=np.float32)

    def _extract_authority(self, url: str, html: str) -> np.ndarray:
        """Extract 9 authority features from URL and HTML."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        is_gov_edu = domain.endswith(".gov") or domain.endswith(".edu")

        has_about = False
        has_contact = False
        author_present = False
        has_citations = False
        has_research_refs = False

        if html:
            soup = BeautifulSoup(html, "html.parser")
            links = [a.get("href", "") for a in soup.find_all("a")]
            has_about = any("about" in (l or "").lower() for l in links)
            has_contact = any("contact" in (l or "").lower() for l in links)
            text = soup.get_text(" ", strip=True).lower()
            author_present = bool(re.search(r"\bby\s+[a-z]", text)) or bool(
                soup.find(attrs={"itemprop": "author"})
            )
            has_citations = "doi" in text or bool(re.search(r"\[[0-9]+\]", text))
            has_research_refs = any(t in text for t in ["arxiv", "pubmed", "doi.org"])

        return np.array([
            10.0 if is_gov_edu else 1.0,    # domain_authority
            1.0 if parsed.scheme == "https" else 0.0,  # https_status
            1.0 if is_gov_edu else 0.0,      # is_gov_edu
            1.0 if has_about else 0.0,        # has_about_page
            1.0 if has_contact else 0.0,      # has_contact_info
            1.0 if author_present else 0.0,   # author_present
            1.0 if has_citations else 0.0,    # has_citations
            1.0 if has_research_refs else 0.0,# has_research_refs
            0.0,                               # domain_age_years (unavailable)
        ], dtype=np.float32)

    def _extract_citability(self, text: str) -> np.ndarray:
        """Extract 9 citability features from plain text (format-independent)."""
        text = (text or "").strip()
        words = re.findall(r"\b\w+\b", text)
        sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
        numeric_tokens = [w for w in words if re.search(r"\d", w)]

        factual_density = (len(numeric_tokens) / max(len(words), 1)) * 100
        specific_claims = sum(
            1 for s in sentences
            if re.search(r"\b(is|are|was|were|has|have)\b", s, re.IGNORECASE)
        )
        self_contained = sum(1 for s in sentences if len(s.split()) >= 8)
        self_contained_ratio = self_contained / max(len(sentences), 1)

        # Flesch-Kincaid grade level
        syllables = sum(self._count_syllables(w) for w in words)
        if sentences and words:
            wps = len(words) / len(sentences)
            spw = syllables / len(words)
            reading_level = max(0.0, 0.39 * wps + 11.8 * spw - 15.59)
        else:
            reading_level = 0.0

        return np.array([
            factual_density,
            float(specific_claims),
            float(len(numeric_tokens)),
            self_contained_ratio,
            1.0 if re.search(r"\b\w+\s+is\s+\w+", text, re.IGNORECASE) else 0.0,
            1.0 if re.search(r"\b(because|therefore|which means|so that|as a result)\b", text, re.IGNORECASE) else 0.0,
            reading_level,
            1.0 if re.search(r"\b(key takeaways|summary|in summary)\b", text, re.IGNORECASE) else 0.0,
            1.0 if re.search(r"\b(faq|frequently asked questions)\b", text, re.IGNORECASE) else 0.0,
        ], dtype=np.float32)

    @staticmethod
    def _count_syllables(word: str) -> int:
        word = word.lower()
        count = 0
        prev_vowel = False
        for char in word:
            is_vowel = char in "aeiouy"
            if is_vowel and not prev_vowel:
                count += 1
            prev_vowel = is_vowel
        if word.endswith("e") and count > 1:
            count -= 1
        return max(count, 1)
```

### Step 4: Use the Scorer

```python
# Initialize once (loads model + scaler)
scorer = CPSScorer(
    checkpoint_path="path/to/best_model.pt",
    scaler_path="path/to/scaler_params.npz",
    openai_api_key="sk-...",
)

# Score Markdown content from your content engine (default format)
result = scorer.score(
    query="best CRM software for small businesses",
    content=article_markdown,               # Markdown from content engine
    content_format="markdown",              # default — can be omitted
    content_url="https://yourdomain.com/best-crm-software",
)

# Or score HTML content
result = scorer.score(
    query="best CRM software for small businesses",
    content=article_html,
    content_format="html",
    content_url="https://yourdomain.com/best-crm-software",
)

print(f"Citation Score: {result['cps_score']}")
print(f"Per-engine: {result['per_engine']}")
```

### Step 5: Integration Pattern for Content Engine

```python
# In your content engine pipeline:

async def generate_and_score_content(query: str) -> dict:
    """Generate content and score it for citability."""

    # 1. Your content engine generates a Markdown article
    article = await content_engine.generate(query=query)

    # 2. Score with CPS model (Markdown input)
    cps_result = scorer.score(
        query=query,
        content=article.markdown,           # Markdown output from engine
        content_format="markdown",
        content_url=article.target_url,
    )

    # 3. Use the score for decisions
    if cps_result["cps_score"] < 0.4:
        # Optionally: regenerate, optimize, or flag for review
        article = await content_engine.optimize_for_citation(
            article, cps_feedback=cps_result
        )
        cps_result = scorer.score(
            query=query,
            content=article.markdown,
            content_format="markdown",
            content_url=article.target_url,
        )

    return {
        "article": article,
        "cps_score": cps_result["cps_score"],
        "per_engine_scores": cps_result["per_engine"],
    }
```

---

## 8. Important Notes

### 8.1 Embedding Model Must Match

The model was trained on **OpenAI `text-embedding-3-small`** (1536 dimensions). Using a different embedding model will produce meaningless results. Do not substitute with `text-embedding-3-large` or any other model.

### 8.2 Feature Standardization Is Critical

Raw features must be standardized using the training set's mean/std from `scaler_params.npz`. Passing unnormalized features will produce incorrect scores. The formula is:

```
normalized = (raw_value - mean) / std
```

### 8.3 BatchNorm Behavior

The FusionEncoder uses `BatchNorm1d` in the sidecar MLP. The model must be in `eval()` mode during inference (which the wrapper above handles). In eval mode, BatchNorm uses running statistics from training, so single-sample inference works correctly.

### 8.4 Content Format: HTML or Markdown

The `score()` method accepts both formats via the `content_format` parameter:
- **`"markdown"`** (default) — Best for content engine output. Markdown is converted to HTML internally using Python's `markdown` library before feature extraction. The conversion preserves all structural signals: `#` headers, `-`/`*`/`1.` lists, `|` tables, fenced code blocks, etc.
- **`"html"`** — Use when content is already HTML. Features are extracted directly from HTML tags.

**Do not pass plain text without structure.** The structural features rely on detecting formatting elements. Plain text with no headers, lists, or paragraphs will produce near-zero structural features, degrading score accuracy.

### 8.5 Cost Considerations

Each `score()` call makes **2 OpenAI API calls** (one for query embedding, one for content embedding). With `text-embedding-3-small`:
- Cost: ~$0.00002 per call ($0.02 per 1M tokens)
- For high-volume usage, cache query embeddings (same query = same embedding).

### 8.6 Latency Profile

Approximate latency breakdown per `score()` call:
- OpenAI embedding API (2 calls): ~200-400ms
- Feature extraction: ~5-10ms
- Model inference (CPU): ~1-2ms
- **Total: ~200-400ms** (dominated by embedding API calls)

For batch scoring, embed all texts in a single batched API call to reduce latency significantly.

### 8.7 Feature Config

The checkpoint stores which feature config was used during training. The wrapper reads this automatically. Currently:
- `option_a` / `option_a_top11`: 11 sidecar features (7 structural + 3 citability)
- `option_b` / `option_b_full31`: 30 sidecar features (12 structural + 9 citability + 9 authority)

The feature config **must match** what the model was trained with. The wrapper handles this from the checkpoint.

---

## 9. Markdown-to-Feature Pipeline Detail

Since your content engine produces Markdown, here is exactly how the conversion and feature extraction works:

### 9.1 Conversion Mapping

The `markdown` library (with extensions) converts Markdown syntax to equivalent HTML tags that the structural feature extractor then counts:

| Markdown Syntax | Converted HTML | Feature Affected |
|-----------------|----------------|-----------------|
| `# Heading` | `<h1>Heading</h1>` | `header_count`, `header_depth` |
| `## Subheading` | `<h2>Subheading</h2>` | `header_count`, `header_depth` |
| `- item` / `* item` | `<ul><li>item</li></ul>` | `has_ul_tags`, `bullet_point_count` |
| `1. item` | `<ol><li>item</li></ol>` | `has_ol_tags`, `bullet_point_count` |
| `\| col \| col \|` | `<table><tr><td>...</td></tr></table>` | `has_table_tags` |
| `` `code` `` / ```` ```code``` ```` | `<code>` / `<pre><code>` | `has_code_blocks` |
| `paragraph text` | `<p>paragraph text</p>` | `paragraph_count`, `avg_paragraph_length` |
| `[text](url)` | `<a href="url">text</a>` | `has_about_page`, `has_contact_info` (authority) |

### 9.2 Processing Flow

```
Content Engine Output (Markdown)
        │
        ▼
┌─ _normalize_to_html() ────────────────┐
│  markdown.convert() with extensions:   │
│  - tables (pipe tables → <table>)      │
│  - fenced_code (``` → <pre><code>)     │
│  - nl2br (line breaks → <br>)          │
│  - sane_lists (strict list parsing)    │
└────────────────────────────────────────┘
        │
        ├──► HTML string ──► _extract_structural() → 12 features
        │                ──► _extract_authority()   → 9 features
        │
        ▼
┌─ _get_plain_text() ───────────────────┐
│  Strip Markdown syntax:                │
│  #, *, **, _, `, [], |, >, etc.        │
│  Produces clean text for embedding     │
│  and citability extraction.            │
└────────────────────────────────────────┘
        │
        ├──► OpenAI embedding (text-embedding-3-small)
        └──► _extract_citability() → 9 features
```

### 9.3 Why Convert Instead of Native Markdown Parsing?

The CPS model was trained on features extracted from HTML content (from web scraping). Converting Markdown to HTML first ensures **feature parity** — the same `<h1>`, `<ul>`, `<table>` tags are counted regardless of whether the source was originally HTML or Markdown. This avoids train/inference distribution mismatch.

---

## 10. API Service Pattern (Optional)

If you want to serve the CPS model as an internal microservice:

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
scorer = None

class ScoreRequest(BaseModel):
    query: str
    content: str
    content_format: str = "markdown"  # "markdown" or "html"
    content_url: str = "https://example.com"
    engines: list[str] | None = None

class ScoreResponse(BaseModel):
    cps_score: float
    per_engine: dict[str, float]
    content_format: str
    model_version: str
    feature_config: str

@app.on_event("startup")
def load_model():
    global scorer
    scorer = CPSScorer(
        checkpoint_path="models/best_model.pt",
        scaler_path="models/scaler_params.npz",
        openai_api_key=os.environ["OPENAI_API_KEY"],
    )

@app.post("/score", response_model=ScoreResponse)
def score_content(req: ScoreRequest) -> ScoreResponse:
    result = scorer.score(
        query=req.query,
        content=req.content,
        content_format=req.content_format,
        content_url=req.content_url,
        engines=req.engines,
    )
    return ScoreResponse(**result)
```

---

## 11. Testing the Integration

After setup, verify the model loads and produces reasonable outputs:

```python
# Quick smoke test
scorer = CPSScorer(
    checkpoint_path="path/to/best_model.pt",
    scaler_path="path/to/scaler_params.npz",
    openai_api_key="sk-...",
)

# --- Test with Markdown (typical content engine output) ---

# A well-structured, factual Markdown article should score higher
good_content_md = """
# 10 Best Project Management Tools for Remote Teams in 2025

Managing remote teams requires robust project management software.
Here are the top tools based on features, pricing, and user reviews.

## 1. Asana

Asana offers task management, timeline views, and integrations with
over 200 apps. Pricing starts at $10.99/user/month.

- Task dependencies
- Custom fields
- Automation rules

## 2. Monday.com

Monday.com provides visual project tracking with customizable workflows.
Plans start at $8/seat/month.

| Feature       | Asana  | Monday.com |
|---------------|--------|------------|
| Starting Price| $10.99 | $8.00      |
| Free Tier     | Yes    | Yes        |
"""

# A vague, poorly structured piece should score lower
weak_content_md = """
Project management is important for teams. There are many tools
available. Some are good and some are not. You should pick one that
works for you. Good luck with your projects.
"""

query = "best project management tools for remote teams"

result_good = scorer.score(query=query, content=good_content_md, content_format="markdown")
result_weak = scorer.score(query=query, content=weak_content_md, content_format="markdown")

print(f"Good content CPS: {result_good['cps_score']}")
print(f"Weak content CPS: {result_weak['cps_score']}")
assert result_good["cps_score"] > result_weak["cps_score"], "Model sanity check failed"

# --- Test with HTML (alternative format) ---

good_content_html = """
<h1>10 Best Project Management Tools for Remote Teams in 2025</h1>
<p>Managing remote teams requires robust project management software.</p>
<h2>1. Asana</h2>
<p>Asana offers task management and integrations. Pricing: $10.99/user/month.</p>
<ul><li>Task dependencies</li><li>Custom fields</li></ul>
"""

result_html = scorer.score(query=query, content=good_content_html, content_format="html")
print(f"HTML content CPS: {result_html['cps_score']}")
```

---

## 12. Summary

| Item | Value |
|------|-------|
| **Model type** | FusionEncoder + CitationPredictor (PyTorch) |
| **Parameters** | ~600K total |
| **Input** | Query text + Content (Markdown or HTML) + Target URL + Engine selection |
| **Output** | CPS score [0.0, 1.0] per engine |
| **Embedding model** | OpenAI `text-embedding-3-small` (1536-dim) |
| **Feature groups** | Structural (12) + Authority (9) + Citability (9) |
| **Artifacts needed** | `best_model.pt` + `scaler_params.npz` |
| **Content formats** | Markdown (default) or HTML |
| **Dependencies** | `torch`, `numpy`, `pydantic`, `openai`, `beautifulsoup4`, `markdown` |
| **Inference latency** | ~200-400ms (dominated by embedding API) |
| **Hardware** | CPU is sufficient |
