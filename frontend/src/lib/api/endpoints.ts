/**
 * API endpoint URL builders.
 *
 * Centralises all backend paths so changes propagate automatically.
 * Every function returns a path string (no base URL — the client adds it).
 */

// ── Auth ────────────────────────────────────────────────────────────────
export const AUTH = {
  register: '/api/v1/auth/register',
  login: '/api/v1/auth/login',
  join: '/api/v1/auth/join',
  me: '/api/v1/auth/me',
  invite: '/api/v1/auth/invite',
} as const;

// ── Health ──────────────────────────────────────────────────────────────
export const HEALTH = {
  health: '/health',
  readiness: '/readiness',
} as const;

// ── Onboarding ─────────────────────────────────────────────────────────
export const ONBOARDING = {
  start: '/api/v1/onboarding/start',
  status: (runId: string) => `/api/v1/onboarding/${runId}/status`,
} as const;

// ── Tasks ───────────────────────────────────────────────────────────────
export const TASKS = {
  list: '/api/v1/tasks',
  get: (taskId: string) => `/api/v1/tasks/${taskId}`,
  cancel: (taskId: string) => `/api/v1/tasks/${taskId}/cancel`,
  streamToken: (taskId: string) => `/api/v1/tasks/${taskId}/stream-token`,
  events: (taskId: string) => `/api/v1/tasks/${taskId}/events`,
} as const;

// ── Companies ──────────────────────────────────────────────────────────
export const COMPANIES = {
  profile: (slug: string) => `/api/v1/companies/${slug}`,
  createProduct: (slug: string) => `/api/v1/companies/${slug}/products`,
  product: (slug: string, productSlug: string) =>
    `/api/v1/companies/${slug}/products/${productSlug}`,
} as const;

// ── Brand Data ─────────────────────────────────────────────────────────
export const BRAND_DATA = {
  researchArtifacts: (slug: string) =>
    `/api/v1/companies/${slug}/research/artifacts`,
  runs: (slug: string) => `/api/v1/companies/${slug}/runs`,
} as const;

// ── Artifacts (raw file access) ────────────────────────────────────────
export const ARTIFACTS = {
  list: (type: string, slug: string) => `/api/v1/artifacts/${type}/${slug}`,
  content: (type: string, slug: string, filename: string) =>
    `/api/v1/artifacts/${type}/${slug}/${filename}`,
} as const;

// ── Gap Analysis Data ──────────────────────────────────────────────────
export const GAP_DATA = {
  summary: (slug: string) => `/api/v1/companies/${slug}/gap-analysis/summary`,
  queries: (slug: string) => `/api/v1/companies/${slug}/gap-analysis/queries`,
  clusters: (slug: string) => `/api/v1/companies/${slug}/gap-analysis/clusters`,
  signals: (slug: string) => `/api/v1/companies/${slug}/gap-analysis/signals`,
  platforms: (slug: string) =>
    `/api/v1/companies/${slug}/gap-analysis/platforms`,
  heatmap: (slug: string) => `/api/v1/companies/${slug}/gap-analysis/heatmap`,
  embeddings: (slug: string) =>
    `/api/v1/companies/${slug}/gap-analysis/embeddings`,
  trend: (slug: string) => `/api/v1/companies/${slug}/gap-analysis/trend`,
} as const;

// ── Content Data ───────────────────────────────────────────────────────
export const CONTENT_DATA = {
  briefs: (slug: string) => `/api/v1/companies/${slug}/content/briefs`,
  brief: (slug: string, briefId: string) =>
    `/api/v1/companies/${slug}/content/briefs/${briefId}`,
  stage: (slug: string, briefId: string, stage: string) =>
    `/api/v1/companies/${slug}/content/briefs/${briefId}/${stage}`,
} as const;

// ── Site Audit ─────────────────────────────────────────────────────────
export const SITE_AUDIT = {
  start: '/api/v1/site-audit/start',
  status: (runId: string) => `/api/v1/site-audit/status/${runId}`,
  audits: (slug: string) => `/api/v1/site-audit/companies/${slug}/audits`,
  audit: (slug: string, auditId: string) =>
    `/api/v1/site-audit/companies/${slug}/audits/${auditId}`,
  findings: (slug: string, auditId: string) =>
    `/api/v1/site-audit/companies/${slug}/audits/${auditId}/findings`,
  pages: (slug: string, auditId: string) =>
    `/api/v1/site-audit/companies/${slug}/audits/${auditId}/pages`,
} as const;

// ── Knowledge Base ─────────────────────────────────────────────────────
export const KNOWLEDGE_BASE = {
  start: '/api/v1/knowledge-base/start',
  health: (slug: string) => `/api/v1/knowledge-base/${slug}/health`,
  status: (runId: string) => `/api/v1/knowledge-base/${runId}/status`,
  approve: (runId: string) => `/api/v1/knowledge-base/${runId}/approve`,
} as const;

// ── Audience Persona ───────────────────────────────────────────────────
export const AUDIENCE_PERSONA = {
  start: '/api/v1/audience-persona/start',
  status: (runId: string) => `/api/v1/audience-persona/${runId}/status`,
  personas: (slug: string) => `/api/v1/audience-persona/${slug}/personas`,
} as const;

// ── Voice Style Guide ──────────────────────────────────────────────────
export const VOICE_STYLE_GUIDE = {
  start: '/api/v1/voice-style-guide/start',
  status: (runId: string) => `/api/v1/voice-style-guide/${runId}/status`,
  guide: (slug: string) => `/api/v1/voice-style-guide/${slug}/guide`,
} as const;

// ── Gap Analysis Pipeline ──────────────────────────────────────────────
export const GAP_ANALYSIS = {
  start: '/api/v1/gap-analysis/start',
  status: (runId: string) => `/api/v1/gap-analysis/${runId}/status`,
} as const;

// ── Content Engine ─────────────────────────────────────────────────────
export const CONTENT_ENGINE = {
  start: '/api/v1/content/v13/start',
  status: (runId: string) => `/api/v1/content/v13/${runId}/status`,
  approveTopics: (runId: string) => `/api/v1/content/v13/${runId}/approve/topics`,
  approveBriefs: (runId: string) => `/api/v1/content/v13/${runId}/approve/briefs`,
  approveContent: (runId: string) =>
    `/api/v1/content/v13/${runId}/approve/content`,
  fromTopics: '/api/v1/content/v13/from-topics',
  topicContentStatus: (slug: string) =>
    `/api/v1/content/v13/${slug}/topic-content-status`,
} as const;

// ── Topic Discovery ────────────────────────────────────────────────────
export const TOPIC_DISCOVERY = {
  start: '/api/v1/topic-discovery/start',
  status: (runId: string) => `/api/v1/topic-discovery/${runId}/status`,
  taxonomy: (slug: string) => `/api/v1/topic-discovery/${slug}/taxonomy`,
  matrix: (slug: string) => `/api/v1/topic-discovery/${slug}/matrix`,
  scoredSubdomains: (slug: string) =>
    `/api/v1/topic-discovery/${slug}/scored-subdomains`,
  personas: (slug: string) => `/api/v1/topic-discovery/${slug}/personas`,
  approveTaxonomy: (runId: string) =>
    `/api/v1/topic-discovery/${runId}/approve/taxonomy`,
  approveSubdomains: (runId: string) =>
    `/api/v1/topic-discovery/${runId}/approve/subdomains`,
  approveMatrix: (runId: string) =>
    `/api/v1/topic-discovery/${runId}/approve/matrix`,
  expand: '/api/v1/topic-discovery/expand',
  expansionStatus: (slug: string) =>
    `/api/v1/topic-discovery/${slug}/expansion-status`,
} as const;

// ── Settings ───────────────────────────────────────────────────────────
export const SETTINGS = {
  team: (slug: string) => `/api/v1/companies/${slug}/settings/team`,
  teamMember: (slug: string, userId: string) =>
    `/api/v1/companies/${slug}/settings/team/${userId}`,
  profile: (slug: string) => `/api/v1/companies/${slug}/settings/profile`,
  pipelineDefaults: (slug: string) =>
    `/api/v1/companies/${slug}/settings/pipeline-defaults`,
} as const;

// ── CMS Integration ───────────────────────────────────────────────────
// Note: CMS endpoints use auth middleware for company context — no slug in paths.
export const CMS = {
  connect: '/api/v1/cms/connect',
  connection: '/api/v1/cms/connection',
  sync: '/api/v1/cms/sync',
  syncedPosts: '/api/v1/cms/synced-posts',
  staleActions: '/api/v1/cms/stale-actions',
  staleToTriage: '/api/v1/cms/stale-to-triage',
  publish: '/api/v1/cms/publish',
  refresh: (cmsPostId: string) => `/api/v1/cms/refresh/${cmsPostId}`,
  publishHistory: '/api/v1/cms/publish-history',
  categories: '/api/v1/cms/categories',
} as const;
