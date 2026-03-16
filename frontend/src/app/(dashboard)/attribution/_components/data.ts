import type { Platform } from '@/types';

// === KPI Demo Data ===
export const kpis = [
  { label: 'AI-Sourced Traffic', value: '12,847', delta: '+34%', deltaType: 'positive' as const },
  { label: 'Demo Requests', value: '47', delta: '+18%', deltaType: 'positive' as const },
  { label: 'Pipeline Generated', value: '$284,000', delta: '+52%', deltaType: 'positive' as const },
  { label: 'Revenue Attributed', value: '$89,400', delta: '+41%', deltaType: 'positive' as const },
];

// === Funnel Data ===
export interface FunnelStepData {
  name: string;
  count: number;
  rate?: string;
}

export const funnelStepsAll: FunnelStepData[] = [
  { name: 'Citation Impression', count: 48200 },
  { name: 'AI Click-Through', count: 12847, rate: '26.7%' },
  { name: 'Site Visit', count: 8419, rate: '65.5%' },
  { name: 'Engagement', count: 3210, rate: '38.1%' },
  { name: 'Conversion', count: 186, rate: '5.8%' },
  { name: 'Revenue', count: 89400, rate: '$481/conv' },
];

// === Platform Data ===
export interface PlatformData {
  impressions: number;
  clickThroughs: number;
  siteVisits: number;
  engagement: number;
  conversions: number;
  revenue: number;
}

export const platformData: Record<Platform, PlatformData> = {
  chatgpt: { impressions: 18300, clickThroughs: 4890, siteVisits: 3200, engagement: 1220, conversions: 71, revenue: 34100 },
  claude: { impressions: 9640, clickThroughs: 2570, siteVisits: 1680, engagement: 642, conversions: 37, revenue: 17900 },
  perplexity: { impressions: 11200, clickThroughs: 3010, siteVisits: 1970, engagement: 752, conversions: 44, revenue: 20800 },
  google_ai_overview: { impressions: 6100, clickThroughs: 1620, siteVisits: 1060, engagement: 405, conversions: 23, revenue: 11200 },
  gemini: { impressions: 2960, clickThroughs: 757, siteVisits: 509, engagement: 191, conversions: 11, revenue: 5400 },
};

export const platformLabels: Record<Platform, string> = {
  chatgpt: 'ChatGPT',
  claude: 'Claude',
  perplexity: 'Perplexity',
  google_ai_overview: 'Google AI Overview',
  gemini: 'Gemini',
};

export const platformColors: Record<Platform, string> = {
  chatgpt: 'var(--accent)',
  claude: '#2e8b8b',
  perplexity: '#d4a843',
  google_ai_overview: 'var(--success)',
  gemini: 'var(--text-tertiary)',
};

export const platformColorHex: Record<Platform, string> = {
  chatgpt: '#5BA4C4',
  claude: '#2e8b8b',
  perplexity: '#d4a843',
  google_ai_overview: '#22c55e',
  gemini: '#94a3b8',
};

export function getFunnelForPlatform(platform: Platform): FunnelStepData[] {
  const d = platformData[platform];
  return [
    { name: 'Citation Impression', count: d.impressions },
    { name: 'AI Click-Through', count: d.clickThroughs, rate: `${((d.clickThroughs / d.impressions) * 100).toFixed(1)}%` },
    { name: 'Site Visit', count: d.siteVisits, rate: `${((d.siteVisits / d.clickThroughs) * 100).toFixed(1)}%` },
    { name: 'Engagement', count: d.engagement, rate: `${((d.engagement / d.siteVisits) * 100).toFixed(1)}%` },
    { name: 'Conversion', count: d.conversions, rate: `${((d.conversions / d.engagement) * 100).toFixed(1)}%` },
    { name: 'Revenue', count: d.revenue, rate: `$${Math.round(d.revenue / d.conversions)}/conv` },
  ];
}

export function getKpisForPlatform(platform: Platform) {
  const d = platformData[platform];
  return [
    { label: 'AI-Sourced Traffic', value: d.clickThroughs.toLocaleString(), delta: '+34%', deltaType: 'positive' as const },
    { label: 'Demo Requests', value: Math.round(d.conversions * 0.25).toString(), delta: '+18%', deltaType: 'positive' as const },
    { label: 'Pipeline Generated', value: `$${Math.round(d.revenue * 3.17).toLocaleString()}`, delta: '+52%', deltaType: 'positive' as const },
    { label: 'Revenue Attributed', value: `$${d.revenue.toLocaleString()}`, delta: '+41%', deltaType: 'positive' as const },
  ];
}

// === Platform breakdown for each funnel stage (for tooltips) ===
export function getPlatformBreakdownForStage(stageIndex: number): { platform: Platform; value: number }[] {
  const keys: (keyof PlatformData)[] = ['impressions', 'clickThroughs', 'siteVisits', 'engagement', 'conversions', 'revenue'];
  const key = keys[stageIndex];
  return (Object.keys(platformData) as Platform[]).map((p) => ({
    platform: p,
    value: platformData[p][key],
  }));
}

// === ROI Table Data ===
export interface ContentROIRow {
  id: string;
  title: string;
  citations: number;
  aiSessions: number;
  conversions: number;
  revenue: number;
  cpsPredicted: number;
  cpsActual: number;
  citationTrend: number[];
  platformBreakdown: Record<Platform, { citations: number; sessions: number; revenue: number }>;
}

export const roiTableData: ContentROIRow[] = [
  {
    id: '1', title: 'How to Choose a No-Code App Builder', citations: 42, aiSessions: 2840, conversions: 34, revenue: 16300,
    cpsPredicted: 0.72, cpsActual: 0.81, citationTrend: [4, 6, 8, 10, 12, 14, 16, 20, 24, 30, 36, 42],
    platformBreakdown: { chatgpt: { citations: 16, sessions: 1080, revenue: 6200 }, claude: { citations: 8, sessions: 568, revenue: 3260 }, perplexity: { citations: 10, sessions: 660, revenue: 3790 }, google_ai_overview: { citations: 5, sessions: 340, revenue: 1960 }, gemini: { citations: 3, sessions: 192, revenue: 1090 } },
  },
  {
    id: '2', title: 'Ship Faster: From Idea to MVP in Hours', citations: 38, aiSessions: 2200, conversions: 28, revenue: 13400,
    cpsPredicted: 0.68, cpsActual: 0.74, citationTrend: [2, 5, 8, 12, 15, 18, 22, 25, 28, 31, 35, 38],
    platformBreakdown: { chatgpt: { citations: 14, sessions: 836, revenue: 5100 }, claude: { citations: 7, sessions: 440, revenue: 2680 }, perplexity: { citations: 9, sessions: 528, revenue: 3120 }, google_ai_overview: { citations: 5, sessions: 264, revenue: 1610 }, gemini: { citations: 3, sessions: 132, revenue: 890 } },
  },
  {
    id: '3', title: 'Why AI-First Development Changes Everything', citations: 31, aiSessions: 1980, conversions: 22, revenue: 10500,
    cpsPredicted: 0.65, cpsActual: 0.71, citationTrend: [3, 5, 7, 10, 13, 16, 19, 22, 24, 26, 29, 31],
    platformBreakdown: { chatgpt: { citations: 12, sessions: 752, revenue: 4000 }, claude: { citations: 6, sessions: 396, revenue: 2100 }, perplexity: { citations: 7, sessions: 475, revenue: 2440 }, google_ai_overview: { citations: 4, sessions: 238, revenue: 1260 }, gemini: { citations: 2, sessions: 119, revenue: 700 } },
  },
  {
    id: '4', title: 'No-Code vs Low-Code: Complete Comparison', citations: 28, aiSessions: 1650, conversions: 19, revenue: 9100,
    cpsPredicted: 0.60, cpsActual: 0.66, citationTrend: [2, 4, 7, 10, 12, 15, 17, 20, 22, 24, 26, 28],
    platformBreakdown: { chatgpt: { citations: 11, sessions: 627, revenue: 3460 }, claude: { citations: 5, sessions: 330, revenue: 1820 }, perplexity: { citations: 6, sessions: 396, revenue: 2120 }, google_ai_overview: { citations: 4, sessions: 198, revenue: 1090 }, gemini: { citations: 2, sessions: 99, revenue: 610 } },
  },
  {
    id: '5', title: 'Building SaaS Products Without Code', citations: 24, aiSessions: 1420, conversions: 16, revenue: 7600,
    cpsPredicted: 0.58, cpsActual: 0.63, citationTrend: [1, 3, 5, 8, 10, 12, 14, 16, 18, 20, 22, 24],
    platformBreakdown: { chatgpt: { citations: 9, sessions: 540, revenue: 2890 }, claude: { citations: 5, sessions: 284, revenue: 1520 }, perplexity: { citations: 5, sessions: 340, revenue: 1770 }, google_ai_overview: { citations: 3, sessions: 170, revenue: 910 }, gemini: { citations: 2, sessions: 86, revenue: 510 } },
  },
  {
    id: '6', title: 'The Rise of AI-Powered Development Tools', citations: 19, aiSessions: 1100, conversions: 12, revenue: 5700,
    cpsPredicted: 0.52, cpsActual: 0.58, citationTrend: [1, 2, 4, 6, 8, 10, 12, 13, 15, 16, 18, 19],
    platformBreakdown: { chatgpt: { citations: 7, sessions: 418, revenue: 2170 }, claude: { citations: 4, sessions: 220, revenue: 1140 }, perplexity: { citations: 4, sessions: 264, revenue: 1330 }, google_ai_overview: { citations: 3, sessions: 132, revenue: 680 }, gemini: { citations: 1, sessions: 66, revenue: 380 } },
  },
  {
    id: '7', title: 'Customer Success Stories: From Zero to Launch', citations: 15, aiSessions: 890, conversions: 9, revenue: 4200,
    cpsPredicted: 0.48, cpsActual: 0.53, citationTrend: [1, 2, 3, 4, 6, 7, 9, 10, 11, 12, 14, 15],
    platformBreakdown: { chatgpt: { citations: 6, sessions: 338, revenue: 1600 }, claude: { citations: 3, sessions: 178, revenue: 840 }, perplexity: { citations: 3, sessions: 214, revenue: 980 }, google_ai_overview: { citations: 2, sessions: 107, revenue: 500 }, gemini: { citations: 1, sessions: 53, revenue: 280 } },
  },
];

// === Trend Chart Data (12 weeks, stacked by platform) ===
export interface TrendWeek {
  week: string;
  chatgpt: number;
  claude: number;
  perplexity: number;
  google_ai_overview: number;
  gemini: number;
  contentPublished: number;
  citationsGained: number;
}

export const trendData: TrendWeek[] = [
  { week: 'W1', chatgpt: 1600, claude: 840, perplexity: 980, google_ai_overview: 530, gemini: 250, contentPublished: 2, citationsGained: 8 },
  { week: 'W2', chatgpt: 1830, claude: 960, perplexity: 1120, google_ai_overview: 605, gemini: 285, contentPublished: 3, citationsGained: 12 },
  { week: 'W3', chatgpt: 1940, claude: 1020, perplexity: 1190, google_ai_overview: 645, gemini: 305, contentPublished: 1, citationsGained: 15 },
  { week: 'W4', chatgpt: 2130, claude: 1120, perplexity: 1310, google_ai_overview: 710, gemini: 330, contentPublished: 4, citationsGained: 18 },
  { week: 'W5', chatgpt: 2360, claude: 1240, perplexity: 1450, google_ai_overview: 785, gemini: 365, contentPublished: 2, citationsGained: 22 },
  { week: 'W6', chatgpt: 2590, claude: 1360, perplexity: 1590, google_ai_overview: 860, gemini: 400, contentPublished: 3, citationsGained: 19 },
  { week: 'W7', chatgpt: 2700, claude: 1420, perplexity: 1660, google_ai_overview: 900, gemini: 420, contentPublished: 2, citationsGained: 24 },
  { week: 'W8', chatgpt: 2970, claude: 1560, perplexity: 1820, google_ai_overview: 990, gemini: 460, contentPublished: 5, citationsGained: 28 },
  { week: 'W9', chatgpt: 3120, claude: 1640, perplexity: 1920, google_ai_overview: 1040, gemini: 480, contentPublished: 3, citationsGained: 31 },
  { week: 'W10', chatgpt: 3390, claude: 1780, perplexity: 2080, google_ai_overview: 1130, gemini: 520, contentPublished: 2, citationsGained: 26 },
  { week: 'W11', chatgpt: 3580, claude: 1880, perplexity: 2200, google_ai_overview: 1190, gemini: 550, contentPublished: 4, citationsGained: 34 },
  { week: 'W12', chatgpt: 3730, claude: 1960, perplexity: 2290, google_ai_overview: 1240, gemini: 580, contentPublished: 3, citationsGained: 38 },
];

// === Donut chart data ===
export const donutData = (Object.keys(platformData) as Platform[]).map((p) => ({
  name: platformLabels[p],
  value: platformData[p].revenue,
  platform: p,
}));

export const totalRevenue = Object.values(platformData).reduce((sum, d) => sum + d.revenue, 0);

// === Conversion path data ===
export const conversionPathData = funnelStepsAll.map((step) => ({
  name: step.name,
  value: step.count,
}));
