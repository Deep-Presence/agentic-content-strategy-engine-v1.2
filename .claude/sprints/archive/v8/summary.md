# Sprint v8 — CPS Model Integration

**Date:** 2026-03-06
**Branch:** `research-agent-v1.2.0`
**Goal:** Integrate the CPS (Citation Signal Predictor) model into Content Engine v1.3 pipeline as Stage 4.5

## Completed

### Phase A: Package Infrastructure
- Created `core/cps_model/__init__.py`, `core/cps_model/model/__init__.py`, `core/cps_model/extractors/__init__.py`
- Added `markdown>=3.5.0` to `pyproject.toml` (torch intentionally NOT added — optional dep)

### Phase B: CPS Scorer (TDD)
- **Tests first**: 26 scorer tests + 14 extractor tests in `tests/cps_model/`
- **Implementation**: `core/cps_model/scorer.py` (~380 lines)
  - `CPSScorer` class wrapping FusionEncoder + CitationPredictor
  - `from_checkpoint()` reads sidecar_input_dim from checkpoint weight shape
  - `_extract_and_standardize()` delegates to 3 extractors, dict→ndarray, standardization with zero-std guard + dim padding
  - `score()` / `score_async()` with `asyncio.to_thread()` for torch inference
  - `get_cps_scorer()` lazy singleton with graceful degradation

### Phase C: Pipeline Integration (TDD)
- **Tests first**: 10 integration tests in `tests/content_engine/test_cps_integration.py`
- **Pipeline modification**: `core/content_engine/pipeline_v13.py`
  - `_score_cps_batch()` async helper scoring all pieces via `asyncio.gather()`
  - Stage 4.5 block between evaluator and HITL-3
  - CPS injected into `eval_summary["cps"]` at HITL-3, auto-approve, and reject paths

### Phase D: Settings
- Added `cps_enabled: bool = True` and `cps_target_weight: float = 0.5` to `settings.py`

### Phase E: Codex Review (gpt-5.3-codex)
- **4 findings**, 1 HIGH fixed:
  1. **HIGH (fixed)**: Sidecar dim mismatch when domain_cite_rate included — added zero-padding in `_extract_and_standardize()`
  2. **MEDIUM (documented)**: CPS stale after edit/rebrief — added comment, acceptable for v1
  3. **LOW**: Domain URL assembly — low risk with bare domains
  4. **LOW**: Unbounded concurrency in gather — max 6 topics in practice
- Fixed no-op event emission test (was `or True`)
- Added sidecar dim padding test

### Phase F: Documentation
- Added Stage 4.5 section to `docs/COMPREHENSIVE_SYSTEM_DOCUMENTATION.md`
- Added CPS score schema to `docs/API_DOCUMENTATION.md` (HITL-3 review section)

## Test Results
- **44 passed, 7 skipped** (torch not installed) across CPS model + integration tests
- **433 passed** in content engine tests (0 regressions, 17 pre-existing tracing failures)

## Files Changed

| File | Action |
|------|--------|
| `core/cps_model/__init__.py` | Created |
| `core/cps_model/model/__init__.py` | Created |
| `core/cps_model/extractors/__init__.py` | Created |
| `core/cps_model/scorer.py` | Created (~380 lines) |
| `core/content_engine/pipeline_v13.py` | Modified (Stage 4.5 + CPS injection) |
| `core/config/settings.py` | Modified (+2 settings) |
| `pyproject.toml` | Modified (+markdown dep) |
| `tests/cps_model/__init__.py` | Created |
| `tests/cps_model/test_scorer.py` | Created (27 tests) |
| `tests/cps_model/test_extractors.py` | Created (14 tests) |
| `tests/content_engine/test_cps_integration.py` | Created (10 tests) |
| `docs/COMPREHENSIVE_SYSTEM_DOCUMENTATION.md` | Modified |
| `docs/API_DOCUMENTATION.md` | Modified |

## Decisions Made
- CPS scores stored in `eval_summary["cps"]` dict — no Pydantic model changes needed
- torch is optional — scorer returns None gracefully when absent
- CPS is informational only — does not gate approval/rejection
- CPS scored once at Stage 4.5 — not re-scored after edit/rebrief loops (acceptable for v1)
