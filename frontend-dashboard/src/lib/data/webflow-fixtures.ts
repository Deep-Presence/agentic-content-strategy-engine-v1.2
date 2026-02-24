// Static fixture data for Webflow gap analysis — sourced from backend results.
// Used to populate the dashboard with real data before live API integration.

import type { ContentBriefItem, Cycle } from '@/types/content';
import type { GapReport, ClusterSpec, GapBrief } from '@/types/gap-analysis';

export const WEBFLOW_COMPANY = {
  slug: 'webflow',
  name: 'Webflow',
  domain: 'webflow.com',
};

export const WEBFLOW_SPA_SCORE = {
  score: 14.975,
  p_value: 0.0000,
  interpretation: 'citation_advantage' as const,
  mean_citation_similarity: 0.6388,
  mean_company_similarity: 0.5008,
  median_citation_similarity: 0.6369,
  median_company_similarity: 0.4893,
  total_queries: 72,
  total_citations: 1422,
  average_gap: 0.1379,
};

export const WEBFLOW_CLUSTERS = [
  { id: 'C1', name: 'Mechanism', queries: 8, citations: 169, avg_word_count: 1740, faq_rate: 0.32, table_rate: 0.21, key_takeaways_rate: 0.10, headers: 0.90, lists: 0.80, stats: 0.62, citations_rate: 0.96, dominant_type: 'blog_or_article', themes: ['build', 'cms', 'code', 'content', 'design', 'development', 'like', 'page', 'platform', 'platforms'] },
  { id: 'C2', name: 'Boundary', queries: 8, citations: 150, avg_word_count: 1596, faq_rate: 0.23, table_rate: 0.29, key_takeaways_rate: 0.16, headers: 0.96, lists: 0.78, stats: 0.75, citations_rate: 0.98, dominant_type: 'blog_or_article', themes: ['business', 'cms', 'code', 'content', 'data', 'enterprise', 'hosting', 'like', 'platform', 'platforms'] },
  { id: 'C3', name: 'Category Comparison', queries: 8, citations: 160, avg_word_count: 1858, faq_rate: 0.36, table_rate: 0.39, key_takeaways_rate: 0.16, headers: 0.96, lists: 0.87, stats: 0.75, citations_rate: 0.96, dominant_type: 'blog_or_article', themes: ['best', 'build', 'business', 'cms', 'code', 'content', 'design', 'development', 'digital', 'headless'] },
  { id: 'C4', name: 'Decision Criteria', queries: 8, citations: 150, avg_word_count: 2055, faq_rate: 0.27, table_rate: 0.24, key_takeaways_rate: 0.10, headers: 0.91, lists: 0.77, stats: 0.71, citations_rate: 0.95, dominant_type: 'blog_or_article', themes: ['brand', 'business', 'cms', 'code', 'content', 'cost', 'digital', 'experience', 'headless', 'like'] },
  { id: 'C5', name: 'Definition', queries: 8, citations: 152, avg_word_count: 1690, faq_rate: 0.24, table_rate: 0.12, key_takeaways_rate: 0.08, headers: 0.92, lists: 0.80, stats: 0.68, citations_rate: 0.93, dominant_type: 'blog_or_article', themes: ['cms', 'code', 'content', 'core', 'design', 'development', 'digital', 'environment', 'experience', 'headless'] },
  { id: 'C6', name: 'Problem/Awareness', queries: 8, citations: 154, avg_word_count: 1685, faq_rate: 0.23, table_rate: 0.13, key_takeaways_rate: 0.10, headers: 0.95, lists: 0.84, stats: 0.73, citations_rate: 0.95, dominant_type: 'blog_or_article', themes: ['content', 'different', 'hosting', 'landing', 'like', 'management', 'marketing', 'multiple', 'page', 'pages'] },
  { id: 'C7', name: 'Best-of/Consideration', queries: 8, citations: 177, avg_word_count: 1748, faq_rate: 0.28, table_rate: 0.29, key_takeaways_rate: 0.12, headers: 0.91, lists: 0.84, stats: 0.71, citations_rate: 0.95, dominant_type: 'blog_or_article', themes: ['best', 'cms', 'content', 'data', 'design', 'enterprise', 'like', 'marketing', 'page', 'platform'] },
  { id: 'C8', name: 'Branded Evaluation', queries: 8, citations: 180, avg_word_count: 1821, faq_rate: 0.38, table_rate: 0.40, key_takeaways_rate: 0.29, headers: 0.92, lists: 0.80, stats: 0.77, citations_rate: 0.97, dominant_type: 'blog_or_article', themes: ['builder', 'cms', 'code', 'content', 'design', 'features', 'framer', 'hubspot', 'marketing', 'platform'] },
  { id: 'C9', name: 'Feature Verification', queries: 8, citations: 130, avg_word_count: 1423, faq_rate: 0.22, table_rate: 0.20, key_takeaways_rate: 0.11, headers: 0.86, lists: 0.80, stats: 0.56, citations_rate: 0.99, dominant_type: 'blog_or_article', themes: ['access', 'cms', 'code', 'content', 'create', 'design', 'like', 'new', 'permissions', 'seo'] },
];

export const WEBFLOW_TOP_GAPS = [
  { id: 'q_45', query: 'How can I migrate off WordPress without losing SEO rankings and backlinks?', cluster: 'Problem/Awareness', cluster_id: 'C6', gap: 0.3233, classification: 'significant_gap' as const, company_sim: 0.4076, citation_sim: 0.7308, target_words: { min: 693, max: 3819 }, reading_level: { min: 8.6, max: 14.2 }, headers: 15, patterns: ['Step-by-Step'], top_domain: 'wpx.net', top_exemplar_sim: 0.8002 },
  { id: 'q_31', query: 'How to estimate total cost of ownership for a no-code website platform', cluster: 'Decision Criteria', cluster_id: 'C4', gap: 0.2878, classification: 'significant_gap' as const, company_sim: 0.4178, citation_sim: 0.7056, target_words: { min: 1636, max: 2353 }, reading_level: { min: 9.7, max: 13.3 }, headers: 27, patterns: ['FAQ', 'Step-by-Step', 'Tables'], top_domain: 'kissflow.com', top_exemplar_sim: 0.7829 },
  { id: 'q_24', query: 'What headless CMS should marketing teams use and why?', cluster: 'Definition', cluster_id: 'C5', gap: 0.2535, classification: 'significant_gap' as const, company_sim: 0.5188, citation_sim: 0.7723, target_words: { min: 977, max: 4268 }, reading_level: { min: 13.0, max: 14.3 }, headers: 37, patterns: ['FAQ', 'Key Takeaways', 'Step-by-Step', 'Tables'], top_domain: 'agilitycms.com', top_exemplar_sim: 0.8775 },
  { id: 'q_36', query: 'What is a headless CMS and how does it help marketing teams?', cluster: 'Definition', cluster_id: 'C5', gap: 0.2535, classification: 'significant_gap' as const, company_sim: 0.5188, citation_sim: 0.7723, target_words: { min: 977, max: 4268 }, reading_level: { min: 13.0, max: 14.3 }, headers: 37, patterns: ['FAQ', 'Tables'], top_domain: 'storyblok.com', top_exemplar_sim: 0.8309 },
  { id: 'q_67', query: 'Do modern website builders support SSO (SAML) and SCIM user provisioning?', cluster: 'Feature Verification', cluster_id: 'C9', gap: 0.2491, classification: 'significant_gap' as const, company_sim: 0.3454, citation_sim: 0.5946, target_words: { min: 726, max: 3306 }, reading_level: { min: 10.2, max: 12.5 }, headers: 44, patterns: ['FAQ', 'Step-by-Step', 'Tables'], top_domain: 'frontegg.com', top_exemplar_sim: 0.6550 },
  { id: 'q_18', query: 'How do no-code website builders compare to building with a headless CMS and Next.js?', cluster: 'Category Comparison', cluster_id: 'C3', gap: 0.2438, classification: 'significant_gap' as const, company_sim: 0.4920, citation_sim: 0.7358, target_words: { min: 1090, max: 1110 }, reading_level: { min: 12.0, max: 14.6 }, headers: 13, patterns: ['Step-by-Step'], top_domain: 'thenewstack.io', top_exemplar_sim: 0.8088 },
  { id: 'q_40', query: 'What are website performance core web vitals and how do site builders impact them?', cluster: 'Definition', cluster_id: 'C5', gap: 0.2290, classification: 'significant_gap' as const, company_sim: 0.4692, citation_sim: 0.6982, target_words: { min: 581, max: 1068 }, reading_level: { min: 11.9, max: 13.3 }, headers: 12, patterns: [], top_domain: 'dynatrace.com', top_exemplar_sim: 0.7621 },
  { id: 'q_37', query: 'What is a design system in the context of website building tools?', cluster: 'Definition', cluster_id: 'C5', gap: 0.1901, classification: 'significant_gap' as const, company_sim: 0.5047, citation_sim: 0.6948, target_words: { min: 772, max: 2404 }, reading_level: { min: 12.9, max: 14.2 }, headers: 14, patterns: [], top_domain: 'webflow.com', top_exemplar_sim: 0.7485 },
  { id: 'q_53', query: 'Best website platforms with enterprise security features (SSO, SOC 2, roles)', cluster: 'Best-of/Consideration', cluster_id: 'C7', gap: 0.1884, classification: 'significant_gap' as const, company_sim: 0.4402, citation_sim: 0.6287, target_words: { min: 3803, max: 3803 }, reading_level: { min: 18.6, max: 18.6 }, headers: 47, patterns: ['FAQ', 'Tables'], top_domain: 'oloid.com', top_exemplar_sim: 0.7124 },
  { id: 'q_38', query: 'What is a staging environment and why do website teams need one?', cluster: 'Definition', cluster_id: 'C5', gap: 0.2307, classification: 'significant_gap' as const, company_sim: 0.4788, citation_sim: 0.7094, target_words: { min: 607, max: 1493 }, reading_level: { min: 11.0, max: 11.0 }, headers: 25, patterns: ['FAQ', 'Step-by-Step'], top_domain: 'marker.io', top_exemplar_sim: 0.7664 },
  { id: 'q_71', query: 'Do hosted website builders provide staging environments and rollback/version history?', cluster: 'Feature Verification', cluster_id: 'C9', gap: 0.1676, classification: 'significant_gap' as const, company_sim: 0.4113, citation_sim: 0.5789, target_words: { min: 1358, max: 1358 }, reading_level: { min: 10.1, max: 10.1 }, headers: 17, patterns: ['FAQ', 'Key Takeaways', 'Step-by-Step'], top_domain: 'dohost.us', top_exemplar_sim: 0.6817 },
  { id: 'q_43', query: 'How can I standardize landing pages so different teams dont break brand design?', cluster: 'Problem/Awareness', cluster_id: 'C6', gap: 0.1606, classification: 'significant_gap' as const, company_sim: 0.4448, citation_sim: 0.6053, target_words: { min: 5258, max: 5258 }, reading_level: { min: 10.8, max: 10.8 }, headers: 33, patterns: [], top_domain: 'klientboost.com', top_exemplar_sim: 0.7033 },
];

export const WEBFLOW_CITABILITY_SCORE = 34;

export const WEBFLOW_CITATION_TREND = [
  { week: 'Jan 6', score: 28 },
  { week: 'Jan 13', score: 30 },
  { week: 'Jan 20', score: 29 },
  { week: 'Jan 27', score: 31 },
  { week: 'Feb 3', score: 32 },
  { week: 'Feb 10', score: 33 },
  { week: 'Feb 17', score: 34 },
  { week: 'Feb 24', score: 34 },
];

export const WEBFLOW_CONTENT_BRIEFS = [
  { id: 'brief-001', title: 'WordPress to Webflow Migration: Complete SEO-Safe Guide', status: 'published' as const, type: 'guide', cluster: 'Problem/Awareness', cluster_id: 'C6', citability_score: 87, word_count: 2450, cycle: 'Week of Feb 10', updated: '2026-02-12T14:30:00Z' },
  { id: 'brief-002', title: 'Total Cost of Ownership: No-Code Website Platforms', status: 'published' as const, type: 'guide', cluster: 'Decision Criteria', cluster_id: 'C4', citability_score: 82, word_count: 2100, cycle: 'Week of Feb 10', updated: '2026-02-13T10:15:00Z' },
  { id: 'brief-003', title: 'Headless CMS for Marketing Teams: What You Need to Know', status: 'review' as const, type: 'blog', cluster: 'Definition', cluster_id: 'C5', citability_score: 91, word_count: 3200, cycle: 'Week of Feb 17', updated: '2026-02-19T16:45:00Z' },
  { id: 'brief-004', title: 'No-Code vs Headless CMS vs Next.js: Decision Framework', status: 'review' as const, type: 'blog', cluster: 'Category Comparison', cluster_id: 'C3', citability_score: 78, word_count: 1095, cycle: 'Week of Feb 17', updated: '2026-02-20T09:30:00Z' },
  { id: 'brief-005', title: 'Enterprise SSO and SCIM in Website Builders', status: 'evaluating' as const, type: 'blog', cluster: 'Feature Verification', cluster_id: 'C9', citability_score: null, word_count: 1800, cycle: 'Week of Feb 24', updated: '2026-02-22T11:00:00Z' },
  { id: 'brief-006', title: 'Core Web Vitals Guide for Site Builder Users', status: 'drafting' as const, type: 'guide', cluster: 'Definition', cluster_id: 'C5', citability_score: null, word_count: 0, cycle: 'Week of Feb 24', updated: '2026-02-23T08:00:00Z' },
  { id: 'brief-007', title: 'Design Systems for Website Teams: Complete Guide', status: 'approved' as const, type: 'guide', cluster: 'Definition', cluster_id: 'C5', citability_score: null, word_count: 0, cycle: 'Week of Feb 24', updated: '2026-02-23T06:00:00Z' },
  { id: 'brief-008', title: 'Enterprise Website Platforms: Security Feature Comparison', status: 'suggested' as const, type: 'blog', cluster: 'Best-of/Consideration', cluster_id: 'C7', citability_score: null, word_count: 0, cycle: null, updated: '2026-02-22T14:00:00Z' },
  { id: 'brief-009', title: 'Staging Environments: Why Every Website Team Needs One', status: 'published' as const, type: 'blog', cluster: 'Definition', cluster_id: 'C5', citability_score: 74, word_count: 1400, cycle: 'Week of Feb 10', updated: '2026-02-11T13:00:00Z' },
  { id: 'brief-010', title: 'Landing Page Standardization: Brand Consistency at Scale', status: 'suggested' as const, type: 'blog', cluster: 'Problem/Awareness', cluster_id: 'C6', citability_score: null, word_count: 0, cycle: null, updated: '2026-02-21T10:00:00Z' },
  { id: 'brief-011', title: 'Webflow vs Framer vs HubSpot CMS: Feature Comparison 2026', status: 'published' as const, type: 'blog', cluster: 'Branded Evaluation', cluster_id: 'C8', citability_score: 89, word_count: 2800, cycle: 'Week of Feb 17', updated: '2026-02-18T15:00:00Z' },
  { id: 'brief-012', title: 'Website Builder Hosting: Built-in vs Vercel vs Netlify', status: 'enriching' as const, type: 'blog', cluster: 'Category Comparison', cluster_id: 'C3', citability_score: null, word_count: 1650, cycle: 'Week of Feb 24', updated: '2026-02-23T07:30:00Z' },
  { id: 'brief-013', title: 'Enterprise RFP Template for Marketing Website Platforms', status: 'suggested' as const, type: 'guide', cluster: 'Decision Criteria', cluster_id: 'C4', citability_score: null, word_count: 0, cycle: null, updated: '2026-02-20T12:00:00Z' },
];

export const WEBFLOW_CYCLES = {
  active: { name: 'Week of Feb 24', start: '2026-02-24', end: '2026-03-02', briefs: ['brief-005', 'brief-006', 'brief-007', 'brief-012'], completed: 0, total: 4 },
  past: [
    { name: 'Week of Feb 17', start: '2026-02-17', end: '2026-02-23', briefs: ['brief-003', 'brief-004', 'brief-011'], completed: 1, total: 3 },
    { name: 'Week of Feb 10', start: '2026-02-10', end: '2026-02-16', briefs: ['brief-001', 'brief-002', 'brief-009'], completed: 3, total: 3 },
  ],
};

export const WEBFLOW_TASKS = [
  { id: 'task-001', pipeline: 'gap_analysis' as const, company_slug: 'webflow', status: 'completed' as const, current_step: null, created_at: '2026-02-18T20:00:00Z', updated_at: '2026-02-18T23:46:00Z' },
  { id: 'task-002', pipeline: 'research' as const, company_slug: 'webflow', status: 'completed' as const, current_step: null, created_at: '2026-02-15T10:00:00Z', updated_at: '2026-02-15T12:30:00Z' },
  { id: 'task-003', pipeline: 'content' as const, company_slug: 'webflow', status: 'completed' as const, current_step: null, created_at: '2026-02-19T08:00:00Z', updated_at: '2026-02-19T14:00:00Z' },
  { id: 'task-004', pipeline: 'content' as const, company_slug: 'webflow', status: 'running' as const, current_step: 'worker_drafting', created_at: '2026-02-23T08:00:00Z', updated_at: '2026-02-23T08:15:00Z' },
];

export const WEBFLOW_COMPANIES = ['webflow', 'ramp', 'carta'];

// ─── Content Pipeline typed data (matches ContentBriefItem / Cycle types) ────

// 13 real content briefs for Webflow
// 4 published, 2 review, 1 evaluating, 1 drafting, 1 enriching, 1 approved, 3 suggested
// 9 blogs, 4 guides | Published avg citability: (87+82+74+89)/4 = 83%
export const WEBFLOW_PIPELINE_BRIEFS: ContentBriefItem[] = [
  {
    id: 'brief-001',
    title: 'How Webflow Compares to WordPress for Enterprise Marketing',
    status: 'published',
    content_type: 'blog',
    cluster: 'C3: Category Comparison',
    target_word_count: 1300,
    citability_score: 87,
    cycle_id: 'cycle-1',
    created_at: '2026-02-08T09:00:00Z',
    updated_at: '2026-02-12T14:00:00Z',
  },
  {
    id: 'brief-002',
    title: 'What Is a Design System in the Context of Website Building Tools?',
    status: 'published',
    content_type: 'blog',
    cluster: 'C5: Definition',
    target_word_count: 950,
    citability_score: 82,
    cycle_id: 'cycle-1',
    created_at: '2026-02-09T10:00:00Z',
    updated_at: '2026-02-13T11:00:00Z',
  },
  {
    id: 'brief-003',
    title: 'Headless CMS for Marketing Teams: A Complete Guide',
    status: 'review',
    content_type: 'guide',
    cluster: 'C7: Best-of/Consideration',
    target_word_count: 1450,
    citability_score: 78,
    cycle_id: 'cycle-2',
    created_at: '2026-02-19T11:00:00Z',
    updated_at: '2026-02-23T06:00:00Z',
  },
  {
    id: 'brief-004',
    title: 'No-Code vs Low-Code: Which Approach Wins for Marketing Websites?',
    status: 'review',
    content_type: 'blog',
    cluster: 'C3: Category Comparison',
    target_word_count: 1200,
    citability_score: 85,
    cycle_id: 'cycle-2',
    created_at: '2026-02-20T08:00:00Z',
    updated_at: '2026-02-23T09:00:00Z',
  },
  {
    id: 'brief-005',
    title: 'How Website Builders Handle Core Web Vitals Performance',
    status: 'evaluating',
    content_type: 'blog',
    cluster: 'C1: Mechanism',
    target_word_count: 1350,
    cycle_id: 'cycle-3',
    created_at: '2026-02-22T07:00:00Z',
    updated_at: '2026-02-23T07:00:00Z',
  },
  {
    id: 'brief-006',
    title: 'Complete Guide to Website Internationalization Without Code',
    status: 'drafting',
    content_type: 'guide',
    cluster: 'C9: Feature Verification',
    target_word_count: 1800,
    cycle_id: 'cycle-3',
    created_at: '2026-02-22T10:00:00Z',
    updated_at: '2026-02-23T01:00:00Z',
  },
  {
    id: 'brief-007',
    title: 'Evaluating Website Platforms for Scalability and Content Velocity',
    status: 'approved',
    content_type: 'blog',
    cluster: 'C4: Decision Criteria',
    target_word_count: 1100,
    cycle_id: 'cycle-3',
    created_at: '2026-02-21T12:00:00Z',
    updated_at: '2026-02-23T05:00:00Z',
  },
  {
    id: 'brief-008',
    title: 'Best Enterprise Website Platforms with SSO and Role-Based Access',
    status: 'suggested',
    content_type: 'guide',
    cluster: 'C7: Best-of/Consideration',
    target_word_count: 1600,
    created_at: '2026-02-22T16:00:00Z',
    updated_at: '2026-02-22T16:00:00Z',
  },
  {
    id: 'brief-009',
    title: 'Product Page Optimization: Features That AI Search Engines Highlight',
    status: 'published',
    content_type: 'blog',
    cluster: 'C9: Feature Verification',
    target_word_count: 800,
    citability_score: 74,
    cycle_id: 'cycle-1',
    created_at: '2026-02-10T10:00:00Z',
    updated_at: '2026-02-14T09:00:00Z',
  },
  {
    id: 'brief-010',
    title: 'When to Choose a Visual Editor vs a Code-First CMS',
    status: 'suggested',
    content_type: 'blog',
    cluster: 'C4: Decision Criteria',
    target_word_count: 1000,
    created_at: '2026-02-22T15:00:00Z',
    updated_at: '2026-02-22T15:00:00Z',
  },
  {
    id: 'brief-011',
    title: 'How Webflow Handles Dynamic Content and CMS Collections',
    status: 'published',
    content_type: 'guide',
    cluster: 'C8: Branded Evaluation',
    target_word_count: 1550,
    citability_score: 89,
    cycle_id: 'cycle-2',
    created_at: '2026-02-15T09:00:00Z',
    updated_at: '2026-02-20T11:00:00Z',
  },
  {
    id: 'brief-012',
    title: 'What Problems Does No-Code Web Design Solve for Growing Teams?',
    status: 'enriching',
    content_type: 'blog',
    cluster: 'C6: Problem/Awareness',
    target_word_count: 1050,
    cycle_id: 'cycle-3',
    created_at: '2026-02-20T14:00:00Z',
    updated_at: '2026-02-23T04:00:00Z',
  },
  {
    id: 'brief-013',
    title: 'Understanding Content Velocity Boundaries in Website Platforms',
    status: 'suggested',
    content_type: 'blog',
    cluster: 'C2: Boundary',
    target_word_count: 1150,
    created_at: '2026-02-23T08:00:00Z',
    updated_at: '2026-02-23T08:00:00Z',
  },
];

// Cycle data — Active: 0/4, Past: 1/3 and 3/3
export const WEBFLOW_ACTIVE_CYCLE: Cycle = {
  id: 'cycle-3',
  name: 'Week of Feb 24',
  start_date: '2026-02-24T00:00:00Z',
  end_date: '2026-03-02T00:00:00Z',
  briefs: WEBFLOW_PIPELINE_BRIEFS.filter((b) =>
    ['brief-005', 'brief-006', 'brief-007', 'brief-012'].includes(b.id)
  ),
  completed_count: 0,
  total_count: 4,
};

export const WEBFLOW_PAST_CYCLES: Cycle[] = [
  {
    id: 'cycle-2',
    name: 'Week of Feb 17',
    start_date: '2026-02-17T00:00:00Z',
    end_date: '2026-02-23T00:00:00Z',
    briefs: WEBFLOW_PIPELINE_BRIEFS.filter((b) =>
      ['brief-003', 'brief-004', 'brief-011'].includes(b.id)
    ),
    completed_count: 1,
    total_count: 3,
  },
  {
    id: 'cycle-1',
    name: 'Week of Feb 10',
    start_date: '2026-02-10T00:00:00Z',
    end_date: '2026-02-16T00:00:00Z',
    briefs: WEBFLOW_PIPELINE_BRIEFS.filter((b) =>
      ['brief-001', 'brief-002', 'brief-009'].includes(b.id)
    ),
    completed_count: 3,
    total_count: 3,
  },
];

// Brief-003 mock content for the Tiptap editor
export const BRIEF_003_CONTENT = `<h1>Headless CMS for Marketing Teams: A Complete Guide</h1>

<p>Marketing teams today face a fundamental tension: they need to publish content faster than ever, but traditional CMS platforms force them to rely on developers for every layout change, new landing page, or campaign update. Headless CMS architecture offers a way to resolve this tension by separating where content is managed from where it is displayed. For marketing organizations evaluating Webflow against headless alternatives like Contentful, Sanity, or Strapi, the decision hinges on how much control your team needs over both content and presentation without writing code.</p>

<h2>What Makes a CMS "Headless" and Why It Matters</h2>

<p>A headless CMS strips away the front-end rendering layer entirely. Content is stored as structured data, delivered via APIs, and rendered by a separate front-end application built in React, Next.js, or another framework. This architecture gives engineering teams enormous flexibility: they can deliver the same content to websites, mobile apps, digital signage, or any channel that consumes an API. However, that flexibility comes at a cost for marketing teams. Without a visual editing interface, marketers must work through developer-mediated workflows to preview content, adjust page layouts, or experiment with new campaign designs. This handoff introduces delays, creates bottlenecks, and ultimately reduces the content velocity that modern B2B marketing demands.</p>

<h2>How Visual Builders Change the Equation</h2>

<p>Visual-first platforms like Webflow take a fundamentally different approach. Instead of separating content from presentation, they unify them in a design canvas that marketers can use directly. Content editors see exactly how their work will appear on the live site, with the ability to adjust spacing, typography, imagery, and responsive behavior without waiting for a developer sprint. The CMS Collections feature in Webflow provides structured content management similar to a headless CMS, with dynamic templates that pull data into designed layouts, while maintaining the visual editing experience that marketing teams need to move quickly. For teams publishing three or more pieces per week, the compounding time savings of eliminating developer handoffs can mean the difference between hitting and missing quarterly content targets.</p>

<h2>Evaluating the Right Fit for Your Team</h2>

<p>The decision between headless and visual CMS architectures is not purely technical. It depends on team composition, content operations maturity, and integration requirements. Teams with dedicated front-end developers who need to serve content across multiple channels, including native mobile apps, may find headless architecture worth the added complexity. But for marketing-led organizations whose primary channel is the web, a visual builder with CMS capabilities delivers faster time-to-publish, lower total cost of ownership, and greater marketing autonomy. When evaluating platforms, focus on three key metrics: time from brief to published page, number of developer hours required per content piece, and the total number of integrations your workflow requires. These metrics will reveal the true operational cost of each approach far more clearly than feature comparison matrices.</p>`;

export const BRIEF_003_DRAFT_CONTENT = `<h1>Headless CMS for Marketing Teams</h1>

<p>Marketing teams need to publish content quickly, but traditional CMS platforms often require developer involvement. Headless CMS is an alternative approach that separates content management from display.</p>

<h2>What is a Headless CMS?</h2>

<p>A headless CMS delivers content via APIs instead of rendering it directly. This gives flexibility but requires technical resources for the front-end.</p>

<h2>Visual Builders as an Alternative</h2>

<p>Platforms like Webflow combine visual editing with CMS features, eliminating the need for developer handoffs.</p>`;

// Citability Score trend data (deterministic)
export const CITABILITY_TREND_DATA = [
  { week: 'Feb 3', score: 68 },
  { week: 'Feb 10', score: 71 },
  { week: 'Feb 17', score: 76 },
  { week: 'Feb 24', score: 79 },
  { week: 'Mar 3', score: 81 },
  { week: 'Mar 10', score: 83 },
  { week: 'Mar 17', score: 85 },
  { week: 'Mar 24', score: 87 },
];

// Velocity data (deterministic)
export const VELOCITY_TREND_DATA = [
  { week: 'Feb 3', completed: 2 },
  { week: 'Feb 10', completed: 3 },
  { week: 'Feb 17', completed: 4 },
  { week: 'Feb 24', completed: 3 },
  { week: 'Mar 3', completed: 3 },
  { week: 'Mar 10', completed: 4 },
  { week: 'Mar 17', completed: 2 },
  { week: 'Mar 24', completed: 3 },
];

// ─── Typed GapReport (adapter from flat fixtures to typed shape) ─────────

function toClusterSpec(c: typeof WEBFLOW_CLUSTERS[number]): ClusterSpec {
  return {
    cluster_id: c.id,
    cluster_name: c.name,
    query_count: c.queries,
    citations_analyzed: c.citations,
    centroid_distance: 0,
    min_similarity_threshold: 0,
    word_count_range: { min: Math.round(c.avg_word_count * 0.4), max: Math.round(c.avg_word_count * 2.2) },
    required_elements: [],
    structural_rates: {
      headers: c.headers,
      lists: c.lists,
      stats: c.stats,
      citations: c.citations_rate,
    },
    avg_word_count: c.avg_word_count,
    faq_rate: c.faq_rate,
    table_rate: c.table_rate,
    key_takeaways_rate: c.key_takeaways_rate,
    dominant_content_type: c.dominant_type,
    dominant_authority_type: 'Industry Expert',
    exemplar_themes: c.themes,
  };
}

function toGapBrief(g: typeof WEBFLOW_TOP_GAPS[number]): GapBrief {
  return {
    query_id: g.id,
    query_text: g.query,
    cluster: g.cluster,
    cluster_id: g.cluster_id,
    gap_score: g.gap,
    gap_classification: g.classification,
    best_company_unit: {
      unit_id: g.id,
      similarity: g.company_sim,
      snippet: '',
    },
    avg_citation_similarity: g.citation_sim,
    content_brief: {
      target_word_count: g.target_words,
      target_reading_level: g.reading_level,
      recommended_header_count: g.headers,
      header_hierarchy: {},
      content_patterns: g.patterns,
      dominant_authority: 'Industry Expert',
      dominant_content_type: 'Guide',
      exemplars_analyzed: 0,
    },
    top_exemplars: [],
  };
}

export const WEBFLOW_GAP_REPORT: GapReport = {
  executive_summary:
    'Webflow faces significant visibility gaps across AI-powered search platforms. ' +
    'Competitors are cited 64% more effectively than Webflow content, particularly in ' +
    'high-intent consideration and comparison queries. The largest gaps exist in Problem/Awareness ' +
    'and Definition clusters where AI platforms consistently reference competitor resources.',
  spa_score: {
    t_statistic: WEBFLOW_SPA_SCORE.score,
    p_value: WEBFLOW_SPA_SCORE.p_value,
    citation_advantage: WEBFLOW_SPA_SCORE.mean_citation_similarity,
    company_advantage: WEBFLOW_SPA_SCORE.mean_company_similarity,
  },
  clusters: WEBFLOW_CLUSTERS.map(toClusterSpec),
  top_gaps: WEBFLOW_TOP_GAPS.map(toGapBrief),
  total_queries: WEBFLOW_SPA_SCORE.total_queries,
  total_citations: WEBFLOW_SPA_SCORE.total_citations,
};
