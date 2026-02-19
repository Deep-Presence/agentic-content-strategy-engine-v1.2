import type { PipelineType, TaskStatus, SSEEventType } from "@/types/api";

/* ── Pipeline stage definitions ────────────────────────────────── */

export const RESEARCH_STAGES = [
  { name: "company", label: "Company Context" },
  { name: "persona", label: "Audience Persona" },
  { name: "style_guide", label: "Writing Style Guide" },
] as const;

export const GAP_ANALYSIS_STEPS = [
  { name: "s1_embed_assets", label: "Embed Assets" },
  { name: "s2_generate_queries", label: "Generate Queries" },
  { name: "s3_search_platforms", label: "Search Platforms" },
  { name: "s4_enrich_citations", label: "Enrich Citations" },
  { name: "s5_embed_content", label: "Embed Content" },
  { name: "s6_analyze", label: "Analyze" },
  { name: "s7_visualize", label: "Visualize" },
  { name: "s8_generate_report", label: "Generate Report" },
] as const;

export const CONTENT_STAGES = [
  { name: "planning", label: "Strategic Planning" },
  { name: "writing", label: "Content Writing" },
  { name: "evaluation", label: "Evaluation" },
  { name: "review", label: "HITL Review" },
] as const;

/* ── Status → color mapping ────────────────────────────────────── */

export const STATUS_COLORS: Record<TaskStatus, { bg: string; text: string; dot: string }> = {
  running:          { bg: "bg-terracotta-50",  text: "text-terracotta-700", dot: "bg-status-running" },
  pending_approval: { bg: "bg-clay-light",     text: "text-clay",           dot: "bg-status-pending" },
  completed:        { bg: "bg-sage-light",     text: "text-sage",           dot: "bg-status-completed" },
  failed:           { bg: "bg-red-50",         text: "text-status-failed",  dot: "bg-status-failed" },
  cancelled:        { bg: "bg-canvas-muted",   text: "text-ink-tertiary",   dot: "bg-status-cancelled" },
  failed_restart:   { bg: "bg-red-50",         text: "text-status-failed",  dot: "bg-status-failed" },
};

/* ── Pipeline display names ────────────────────────────────────── */

export const PIPELINE_LABELS: Record<PipelineType, string> = {
  research: "Research",
  gap_analysis: "Gap Analysis",
  content: "Content Generation",
};

/* ── Artifact type labels ──────────────────────────────────────── */

export const ARTIFACT_TYPE_LABELS: Record<string, string> = {
  company_context: "Company Context",
  personas: "Personas",
  style_guides: "Style Guides",
  gap_analysis: "Gap Analysis",
  content: "Content",
};

export const VALID_ARTIFACT_TYPES = [
  "company_context",
  "personas",
  "style_guides",
  "gap_analysis",
  "content",
] as const;

/* ── SSE event types ───────────────────────────────────────────── */

export const ALL_SSE_EVENTS: SSEEventType[] = [
  "pipeline_start",
  "stage_start",
  "pending_approval",
  "approval_received",
  "stage_complete",
  "completed",
  "failed",
  "cancelled",
];

export const TERMINAL_SSE_EVENTS: SSEEventType[] = [
  "completed",
  "failed",
  "cancelled",
];

/* ── Visualization labels ──────────────────────────────────────── */

export const VIZ_LABELS: Record<string, string> = {
  "gap_heatmap.html": "Gap Heatmap",
  "umap.html": "UMAP Projection",
  "radar.html": "Cluster Radar",
  "treemap.html": "Citation Treemap",
  "gap_distribution.html": "Gap Distribution",
  "embedding_space.html": "Embedding Space",
  "citation_treemap.html": "Citation Treemap",
  "cluster_radar.html": "Cluster Radar",
  "similarity_distribution.html": "Similarity Distribution",
  "tsne_embedding_space.html": "t-SNE Embedding Space",
  "umap_embedding_space.html": "UMAP Embedding Space",
  "tsne_clustered.html": "t-SNE Clustered",
  "umap_clustered.html": "UMAP Clustered",
};
