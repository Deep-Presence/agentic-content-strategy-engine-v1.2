# API Schemas

> **Location:** `api/schemas/`
> **Owner:** API
> **Dependencies:** Pydantic v2
> **Dependents:** All API routers
> **Last Updated:** 2026-04-09

## Overview

21 schema files defining request/response models for all API endpoints. Schemas are Pydantic v2 BaseModel classes that validate input and shape output. They mirror but are separate from `core/models/` — API schemas are the external contract, core models are the internal contract.

## File Inventory

| File | Key Models | Purpose |
|------|-----------|---------|
| `common.py` | `PipelineRunResponse`, `TaskResponse`, `TaskListResponse`, `ErrorResponse` | Shared across all pipelines |
| `analytics.py` | `AuthorizeResponse`, `ConnectionResponse`, `SyncResponse`, `TrafficDataResponse` | GA4 integration |
| `audience_persona.py` | `PersonaBriefApprovalRequest`, `PersonaProfileApprovalRequest`, `PersonaListItem` | AP pipeline HITL |
| `brand_data.py` | `ResearchArtifactsResponse`, `RunHistoryResponse`, `SPATrendResponse` | Brand Hub data |
| `cms.py` | `CMSConnectRequest`, `CMSPublishRequest`, `CMSSyncedPostSummary`, `StaleContentAction` | CMS integration |
| `company.py` | `CompanyProfileResponse`, `ProductCreateRequest`, `ProductDetailResponse` | Company/product management |
| `content_data.py` | `ContentBriefListResponse`, `ContentBriefDetailResponse`, `StageContentResponse` | Content Studio data |
| `content_inventory.py` | `ContentInventoryItem`, `ContentInventoryListResponse`, `ContentInventoryStats` | Content registry |
| `content_performance.py` | `ContentPerformanceTableResponse`, `VelocityInsightsResponse`, `ContentDetailResponse` | Performance metrics |
| `content_to_prompt.py` | `GeneratePromptsRequest`, `PagePromptsResponse`, `PendingPromptsResponse` | Prompt generation |
| `content_v13.py` | `ContentStartRequestV13`, `TopicApprovalRequest`, `BriefApprovalRequest`, `TopicContentStartRequest` | Content Engine v1.3 |
| `cps.py` | `CPSScoreRequest`, `CPSScoreResponse` | CPS scoring |
| `gap_data.py` | `GapSummaryResponse`, `QueryListResponse`, `ClusterSpecResponse` | Gap analysis data |
| `knowledge_docs.py` | `KnowledgeDocResponse`, `KnowledgeDocListResponse` | Knowledge docs |
| `onboarding.py` | `OnboardingStartRequest` | Onboarding pipeline |
| `research_orchestrator.py` | `ResearchOrchestratorStartRequest` | Research orchestrator |
| `settings.py` | `TeamListResponse`, `CompanyProfileSettingsResponse`, `PipelineDefaultsResponse` | Settings page |
| `site_audit.py` | `AuditSummaryResponse`, `AuditDetailResponse`, `AuditFindingsResponse` | Site audit data |
| `topic_discovery.py` | `TaxonomyApprovalRequest`, `MatrixApprovalRequest`, `ScoredSubdomainsResponse` | TD pipeline |
| `voice_style_guide.py` | `AuthorApprovalRequest`, `ApprovalResponseVSG` | VSG pipeline |

## Common Response Patterns

```python
# Pipeline launch
PipelineRunResponse(run_id, pipeline, company_slug, product_slug, effective_slug, status, created_at)

# Task status
TaskResponse(run_id, pipeline, status, current_step, progress_pct, result, error, approval_payload)

# Error
ErrorResponse(detail: str, error_code: str)
```
