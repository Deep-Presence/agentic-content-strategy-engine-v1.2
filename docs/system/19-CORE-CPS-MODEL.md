# CPS Model — Citation Signal Predictor

> **Location:** `core/cps_model/`
> **Owner:** Core
> **Dependencies:** PyTorch, numpy, OpenAI embeddings
> **Dependents:** Pipeline 4 (Topic Discovery scoring), API CPS endpoints
> **Last Updated:** 2026-04-09

## Overview

The CPS (Citation Signal Predictor) model is a neural network that predicts whether AI search engines will cite a given piece of content for a given query. It uses a three-stream fusion encoder (semantic projection + structural sidecar + engine conditioning) feeding into a dual-head predictor (contrastive target + selection rate regression).

## Architecture

```
Input:
  query_embedding [1536]    structural_features [11-31]    engine_one_hot [4]
         │                         │                              │
    Linear(1536→256)          MLP(N→64→128)                 Linear(4→16)
    ReLU + LayerNorm         ReLU + BatchNorm               ReLU
         │                    + Dropout                          │
         └─────────────────────┬──────────────────────────────────┘
                               │ Concatenate [400]
                               │
                    ┌──────────▼──────────┐
                    │    Shared Trunk     │
                    │  Linear(400→256)    │
                    │  → ReLU → Dropout   │
                    │  → Linear(256→128)  │
                    │  → ReLU → Dropout   │
                    └──────────┬──────────┘
                               │
               ┌───────────────┼───────────────┐
               │                               │
    Per-Engine Heads [4]            Selection Rate Head
    Linear(128→400)                 Linear(400→64→1)
    → target embedding              → Sigmoid → SR score
               │                               │
               ▼                               ▼
    cosine_sim(target, content)         Content quality prior
               │                               │
               └───────┬───────────────────────┘
                       │ Blend
    CPS = target_weight * cosine_cps + (1 - target_weight) * sr_cps
```

## File Structure

| File | Purpose |
|------|---------|
| `config.py` | Hyperparameter Pydantic models |
| `scorer.py` | Production inference wrapper (`CPSScorer`) |
| `model/fusion_encoder.py` | Three-stream encoder |
| `model/citation_predictor.py` | Shared trunk + dual heads |
| `model/feature_selector.py` | Feature selection configs (Option A: 11, Option B: 31) |
| `extractors/structural.py` | HTML → 12 structural features |
| `extractors/citability.py` | Text → 9 citability features |
| `extractors/authority.py` | URL + HTML → 9 authority features |

## Feature Groups

| Group | Features | Example |
|-------|----------|---------|
| Structural (12) | header_count, table_count, paragraph_count, bullet_count, avg_sentence_length | HTML structure |
| Citability (9) | factual_density, self_contained_ratio, reading_level, has_faq, has_key_takeaways | Content quality |
| Authority (9) | domain_authority, has_https, is_gov_edu, has_author, citation_density | Trust signals |

**Option A** (11 features): 7 structural + 3 citability (lightweight)
**Option B** (31 features): all 12 + 9 + 9 (comprehensive)

## Inference

```python
scorer = CPSScorer.from_checkpoint("path/to/checkpoint.pt")
result = scorer.score(
    query_texts=["best expense management software"],
    content_markdown="# Top 10 Expense Tools...",
    content_url="https://acme.com/blog/expense-tools"
)
# Returns: {"cps_score": 0.73, "per_engine": {...}, "per_query": [...]}
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `cps_enabled` | `True` | Enable CPS scoring |
| `cps_target_weight` | `0.5` | Blend weight between contrastive and regression signals |
