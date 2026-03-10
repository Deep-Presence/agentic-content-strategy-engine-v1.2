# Skill: Data Model Changes

> Model changes cascade through the entire pipeline. One missing default can break deserialization of every existing artifact. Follow this checklist with zero exceptions.

---

## The Golden Rule

**Every new field MUST have a default value.** No exceptions. Existing JSON artifacts in `artifacts/gap_analysis/{client}/` were written before your field existed. If they can't deserialize without it, you've broken production.

```python
# CORRECT — has default, backward compatible
class QueryGap(BaseModel):
    structural_signals_count: int = 0  # new field, defaults to 0

# WRONG — will crash on every existing artifact
class QueryGap(BaseModel):
    structural_signals_count: int  # no default → ValidationError on old data
```

---

## Pre-Change Checklist

Before changing ANY model in `core/models/`, complete every step:

### 1. Identify the Model and Its File

All gap analysis models live in `core/models/gap_analysis.py`. Research models are in `core/models/artifacts.py` and `core/models/personas.py`.

### 2. Find All Serialization Points

Search the codebase for every place the model is written to disk:

```bash
# Find all .model_dump() calls
grep -rn "model_dump" core/ scripts/ --include="*.py"

# Find all json.dumps with model data
grep -rn "json.dumps" core/ scripts/ --include="*.py"

# Find all .model_dump_json() calls
grep -rn "model_dump_json" core/ scripts/ --include="*.py"
```

**Known serialization points in the gap analysis pipeline:**

| Model | Written By | File Format | Location |
|-------|-----------|-------------|----------|
| `SemanticUnit` | s1 | JSON list | `{slug}/company_embeddings.json` |
| `GeneratedQuery` | s2, s5 | JSON list | `{slug}/queries.json`, `{slug}/embeddings/queries_with_embeddings.json` |
| `PlatformResult` | s3 | JSONL per engine | `{slug}/platform_results/{engine}_results.jsonl` |
| `EnrichedCitation` | s4, s5 | JSON list | `{slug}/enriched_citations.json`, `{slug}/embeddings/citations_with_embeddings.json` |
| `AnalysisResult` | s6 | Single JSON | `{slug}/analysis.json` |
| `GapReport` | s8 | MD + JSON | `{slug}/gap_report.{md,json}`, `{slug}/generation_spec.{md,json}` |

### 3. Find All Deserialization Points

Search for every place the model is read from disk:

```bash
# Find all direct model construction from dicts
grep -rn "model_cls(\*\*" core/ scripts/ --include="*.py"
grep -rn "json.loads" core/ scripts/ --include="*.py"

# Find the pipeline skip_steps loading (critical)
grep -rn "_load_json_list" core/gap_analysis/pipeline.py
```

**Known deserialization points:**

| Model | Read By | Code Location |
|-------|---------|---------------|
| `SemanticUnit` | s6 (via pipeline skip) | `pipeline.py: _load_json_list()` |
| `GeneratedQuery` | s3, s5, s6, s8 (via pipeline) | `pipeline.py: _load_json_list()` |
| `PlatformResult` | s4 (via pipeline skip) | `pipeline.py: PlatformResult(**json.loads(line))` |
| `EnrichedCitation` | s5, s6, s8 (via pipeline) | `pipeline.py: _load_json_list()` |
| `AnalysisResult` | s8 (via pipeline skip) | `pipeline.py: AnalysisResult(**json.loads(...))` |
| `QueryCluster` | s2 | `s2: _load_taxonomy()` |

### 4. Find All Consumers of the Model

Search for imports and attribute access:

```bash
# Find all imports of the model
grep -rn "from core.models.gap_analysis import" core/ scripts/ tests/ --include="*.py" | grep "YourModelName"

# Find all attribute access (e.g., if adding a new field)
grep -rn "\.your_new_field" core/ scripts/ tests/ --include="*.py"
```

### 5. Check Existing Artifacts Can Still Load

```python
# Quick validation script — run this BEFORE committing
import json
from pathlib import Path
from core.models.gap_analysis import YourModel

artifact_path = Path("artifacts/gap_analysis/ramp/your_file.json")
data = json.loads(artifact_path.read_text())

if isinstance(data, list):
    for item in data:
        YourModel(**item)  # Must not throw
else:
    YourModel(**data)  # Must not throw

print("✓ Existing artifacts still deserialize")
```

---

## Change Types and Their Risk Levels

### LOW RISK: Adding an Optional field with default
```python
# Safe — old artifacts missing this field will get the default
new_field: Optional[str] = None
new_count: int = 0
new_list: List[str] = Field(default_factory=list)
```

### MEDIUM RISK: Changing a field's type
```python
# BEFORE
header_count: int = 0

# AFTER — changing to a more complex type
# REQUIRES: checking every consumer that accesses .header_count
header_counts: Dict[str, int] = Field(default_factory=dict)
# BUT: the old field name "header_count" is gone → breaks old consumers
```
**Mitigation:** Keep the old field as deprecated, add the new field alongside it:
```python
header_count: int = 0  # deprecated, kept for backward compat
header_counts: Dict[str, int] = Field(default_factory=dict)  # new
```

### HIGH RISK: Removing a field
```python
# NEVER remove a field without checking every consumer
# Search: grep -rn "\.field_name" core/ scripts/ tests/
# If any code accesses it → you can't remove it yet
```

### HIGH RISK: Renaming a field
```python
# Renaming is effectively remove + add — both must be handled
# Use Pydantic v2 alias for backward compat:
class MyModel(BaseModel):
    new_name: int = Field(0, alias="old_name")
    
    model_config = ConfigDict(populate_by_name=True)
```

### CRITICAL RISK: Changing HttpUrl behavior
```python
# Pydantic v2 HttpUrl serializes as Url object, not string
# Always use model_dump(mode="json") to get string URLs
# If you see str(citation.url) in code, it works but watch for double-stringification
```

---

## Decision Format for Model Changes

Any model change REQUIRES the decision protocol. Use this template:

```
DECISION NEEDED: Model Change

WHAT:
  Model: {ModelName} in core/models/{file}.py
  Change: {Add field / Change type / Remove field / Rename field}
  Field: {field_name}: {old_type} → {new_type}
  Default: {default value}

WHY:
  {Why this change is needed — link to task/sprint goal}

IMPACT ANALYSIS:
  Serialization points: {N files write this model}
  Deserialization points: {N files read this model}
  Consumers: {N files access the changed field}
  Existing artifacts: {Will they still load? Yes/No}

ALTERNATIVES:
  1. {Alternative approach that doesn't require model change}
  2. {Different model change that's less risky}

BACKWARD COMPATIBILITY:
  - Existing Ramp artifacts: {✓ loads / ✗ breaks}
  - Existing Carta artifacts: {✓ loads / ✗ breaks}
  - Pipeline skip_steps: {✓ works / ✗ breaks}

REVERSIBLE: {Yes — can revert by removing field / No — requires data migration}

MIGRATION NEEDED: {Yes / No}
  If yes: {describe the migration steps}
```

**Wait for Aryan's approval before proceeding.**

---

## Post-Change Verification

After implementing the model change:

### 1. Roundtrip Test
```python
def test_model_roundtrip_with_existing_artifact():
    raw = json.loads(Path("tests/fixtures/ramp/{file}.json").read_text())
    items = [Model(**item) for item in raw]  # Must not throw
    for item in items:
        reserialized = json.loads(item.model_dump_json())
        Model(**reserialized)  # Double roundtrip
```

### 2. Pipeline Skip Test
```bash
# Run pipeline with skip_steps to test artifact loading
python -c "
from core.gap_analysis.pipeline import run_gap_analysis
from core.models.gap_analysis import GapAnalysisInput
# Load with all steps skipped to test deserialization
run_gap_analysis(GapAnalysisInput(company_name='ramp', domain='ramp.com'), skip_steps=[1,2,3,4,5,6,7,8])
"
```

### 3. Full grep for old field name (if renamed/removed)
```bash
grep -rn "old_field_name" core/ scripts/ tests/ --include="*.py"
# Must return 0 results (or only in backward-compat aliases)
```

---

## Known Model Gotchas in This Codebase

1. **`HttpUrl` serialization** — Pydantic v2's `HttpUrl` is a `Url` object, not a string. Always use `model_dump(mode="json")` when writing to JSON, and `str(field)` when using in string operations.

2. **`List[float]` embeddings** — Embedding vectors are 3072-dimensional. JSON serialization of these is huge. When testing, you can skip embedding comparison or use `[:10]` prefix checks.

3. **`Field(default_factory=list)`** — Required for mutable defaults. Never use `field: List[str] = []` — that shares the same list instance across all model instances.

4. **`Optional` vs default** — `Optional[str] = None` means the field can be `None` in the JSON. `str = ""` means it's always a string. Choose based on whether `None` has semantic meaning (e.g., "not yet computed" vs "empty result").

5. **Nested models** — `AnalysisResult` contains `List[QueryGap]`, `List[SpaResult]`, `List[ClusterContentSpec]`. Changing any nested model affects `AnalysisResult` serialization too. Always test the top-level model roundtrip.