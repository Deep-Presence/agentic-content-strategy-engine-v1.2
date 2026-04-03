import type { Platform } from '@/types';

// === Types ===

export interface PromptRow {
  id: string;
  text: string;
  topic: string;
  topicColor: string;
  tags: string[];
  queryFanouts: number;
  mentionRate: number;
  mentionDelta: number;
  citationRate: number;
  citationDelta: number;
  volume: number[];
}

export interface CompetitorMention {
  rank: number;
  brand: string;
  domain: string;
  mentions: number;
  mentionRate: number;
  mentionDelta: number;
  isYou: boolean;
}

export interface PlatformMentionRate {
  platform: Platform;
  label: string;
  domain: string;
  mentionRate: number;
}

export interface QueryFanout {
  query: string;
  observations: number;
}

export interface AnswerHistoryRow {
  id: string;
  date: string;
  persona: string;
  platform: Platform;
  platformLabel: string;
  platformDomain: string;
  answerPreview: string;
  cited: boolean;
  mentioned: boolean;
  competitorDomains: string[];
  fullAnswer: string;
  citations: string[];
  mentionedBrands: { domain: string; name: string; checked: boolean }[];
}

// === Prompts — exact spec order ===

export const PROMPTS: PromptRow[] = [
  { id: 'p1', text: 'Lovable vs Bolt.new comparison', topic: 'AI App Builder Evaluation', topicColor: '#5BA4C4', tags: ['branded', 'comparison'], queryFanouts: 7, mentionRate: 0.679, mentionDelta: 0.071, citationRate: 0.893, citationDelta: 0.036, volume: [30, 32, 35, 33, 38, 40, 42] },
  { id: 'p2', text: 'Best AI app builder for startups', topic: 'AI App Builder Evaluation', topicColor: '#5BA4C4', tags: ['branded'], queryFanouts: 14, mentionRate: 0.536, mentionDelta: 0.143, citationRate: 0.643, citationDelta: 0.107, volume: [25, 28, 32, 35, 38, 42, 45] },
  { id: 'p3', text: 'Can AI build a full-stack web application?', topic: 'Vibe Coding & Prompt-to-App', topicColor: '#34B27B', tags: [], queryFanouts: 10, mentionRate: 0.464, mentionDelta: 0.107, citationRate: 0.571, citationDelta: 0.071, volume: [35, 38, 42, 40, 45, 48, 50] },
  { id: 'p4', text: 'AI app builder for non-technical founders', topic: 'AI App Builder Evaluation', topicColor: '#5BA4C4', tags: ['persona'], queryFanouts: 8, mentionRate: 0.393, mentionDelta: 0.071, citationRate: 0.500, citationDelta: 0.107, volume: [15, 18, 20, 22, 25, 28, 30] },
  { id: 'p5', text: 'What is the best AI phone agent for healthcare?', topic: 'Clinic & Patient Admin Automation', topicColor: '#DC7B18', tags: [], queryFanouts: 6, mentionRate: 0.333, mentionDelta: -0.131, citationRate: 0.481, citationDelta: -0.090, volume: [20, 18, 22, 19, 15, 14, 12] },
  { id: 'p6', text: 'How to deploy AI-generated app to production', topic: 'Deployment & DevOps', topicColor: '#8B7EC8', tags: [], queryFanouts: 15, mentionRate: 0.321, mentionDelta: 0.071, citationRate: 0.821, citationDelta: 0.143, volume: [18, 20, 22, 25, 28, 30, 32] },
  { id: 'p7', text: 'Prompt-to-app platform comparison 2026', topic: 'AI App Builder Evaluation', topicColor: '#5BA4C4', tags: ['comparison'], queryFanouts: 14, mentionRate: 0.286, mentionDelta: -0.071, citationRate: 0.679, citationDelta: 0.143, volume: [22, 25, 28, 24, 30, 28, 26] },
  { id: 'p8', text: 'How does an AI phone assistant work for clinics?', topic: 'Clinic & Patient Admin Automation', topicColor: '#DC7B18', tags: [], queryFanouts: 6, mentionRate: 0.250, mentionDelta: 0.036, citationRate: 0.821, citationDelta: -0.036, volume: [12, 15, 18, 14, 16, 20, 22] },
  { id: 'p9', text: 'Can AI answer patient phone calls?', topic: 'Clinic & Patient Admin Automation', topicColor: '#DC7B18', tags: [], queryFanouts: 10, mentionRate: 0.214, mentionDelta: -0.036, citationRate: 0.821, citationDelta: -0.036, volume: [8, 10, 12, 15, 14, 11, 9] },
  { id: 'p10', text: 'What is vibe coding?', topic: 'Vibe Coding & Prompt-to-App', topicColor: '#34B27B', tags: ['definition'], queryFanouts: 12, mentionRate: 0.179, mentionDelta: 0.036, citationRate: 0.214, citationDelta: -0.036, volume: [40, 45, 50, 48, 55, 60, 58] },
  { id: 'p11', text: 'AI app builder with database integration', topic: 'Feature Evaluation', topicColor: '#DC7B18', tags: ['feature'], queryFanouts: 9, mentionRate: 0.179, mentionDelta: -0.036, citationRate: 0.214, citationDelta: -0.036, volume: [10, 12, 14, 12, 15, 13, 11] },
  { id: 'p12', text: 'AI app builder security features', topic: 'Security & Compliance', topicColor: '#E5484D', tags: ['security'], queryFanouts: 8, mentionRate: 0.107, mentionDelta: 0.000, citationRate: 0.036, citationDelta: 0.036, volume: [5, 6, 4, 7, 8, 6, 5] },
  { id: 'p13', text: 'RBAC in AI-generated applications', topic: 'Security & Compliance', topicColor: '#E5484D', tags: ['security', 'enterprise'], queryFanouts: 6, mentionRate: 0.036, mentionDelta: 0.036, citationRate: 0.000, citationDelta: 0.000, volume: [2, 3, 2, 4, 3, 2, 3] },
  { id: 'p14', text: 'SOC 2 compliance for AI development platforms', topic: 'Security & Compliance', topicColor: '#E5484D', tags: ['enterprise', 'compliance'], queryFanouts: 5, mentionRate: 0.000, mentionDelta: 0.000, citationRate: 0.000, citationDelta: 0.000, volume: [1, 2, 1, 2, 3, 2, 1] },
  { id: 'p15', text: 'Leading AI assistant companies compared', topic: 'AI App Builder Evaluation', topicColor: '#5BA4C4', tags: ['comparison'], queryFanouts: 14, mentionRate: 0.000, mentionDelta: 0.000, citationRate: 0.000, citationDelta: 0.000, volume: [8, 10, 12, 11, 14, 12, 10] },
];

// === Topics (derived) ===

export const TOPICS = Array.from(new Set(PROMPTS.map((p) => p.topic))).map((topic) => {
  const prompts = PROMPTS.filter((p) => p.topic === topic);
  return {
    name: topic,
    color: prompts[0].topicColor,
    count: prompts.length,
    avgMentionRate: prompts.reduce((s, p) => s + p.mentionRate, 0) / prompts.length,
    avgCitationRate: prompts.reduce((s, p) => s + p.citationRate, 0) / prompts.length,
  };
});

// === Competitor data ===

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function getCompetitorMentions(_promptId: string): CompetitorMention[] {
  return [
    { rank: 1, brand: 'Lovable', domain: 'lovable.dev', mentions: 6, mentionRate: 0.21, mentionDelta: 0.016, isYou: true },
    { rank: 2, brand: 'Bolt.new', domain: 'bolt.new', mentions: 4, mentionRate: 0.14, mentionDelta: -0.005, isYou: false },
    { rank: 3, brand: 'Cursor', domain: 'cursor.com', mentions: 2, mentionRate: 0.07, mentionDelta: 0.001, isYou: false },
    { rank: 4, brand: 'Replit', domain: 'replit.com', mentions: 1, mentionRate: 0.04, mentionDelta: 0.000, isYou: false },
    { rank: 5, brand: 'V0.dev', domain: 'v0.dev', mentions: 1, mentionRate: 0.04, mentionDelta: -0.011, isYou: false },
  ];
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function getPlatformMentionRates(_promptId: string): PlatformMentionRate[] {
  return [
    { platform: 'chatgpt', label: 'ChatGPT', domain: 'openai.com', mentionRate: 0.00 },
    { platform: 'gemini', label: 'Gemini', domain: 'gemini.google.com', mentionRate: 0.00 },
    { platform: 'perplexity', label: 'Perplexity', domain: 'perplexity.ai', mentionRate: 0.00 },
    { platform: 'google_ai_overview', label: 'Google AI Mode', domain: 'google.com', mentionRate: 0.86 },
    { platform: 'claude', label: 'Claude', domain: 'anthropic.com', mentionRate: 0.14 },
  ];
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function getQueryFanouts(_promptId: string): QueryFanout[] {
  return [
    { query: 'Can AI answer patient phone calls healthcare AI answering', observations: 3 },
    { query: 'AI phone answering for patient calls healthcare what solutions', observations: 1 },
    { query: 'AI answering phone calls for patients healthcare call handling', observations: 1 },
    { query: 'AI answering patient calls medical office virtual assistant', observations: 1 },
    { query: 'best AI phone assistant for medical clinics 2026', observations: 2 },
    { query: 'automated phone answering service for healthcare providers', observations: 1 },
  ];
}

// === Platform info ===

export const PLATFORM_INFO: Record<Platform, { label: string; domain: string }> = {
  chatgpt: { label: 'ChatGPT', domain: 'openai.com' },
  claude: { label: 'Claude', domain: 'anthropic.com' },
  perplexity: { label: 'Perplexity', domain: 'perplexity.ai' },
  google_ai_overview: { label: 'Google AI Mode', domain: 'google.com' },
  gemini: { label: 'Gemini', domain: 'gemini.google.com' },
};

// === Level 2 citations — exact spec list ===

const CITATION_DOMAINS = [
  'lovable.dev', 'lovable.dev', 'heidihealth.com', 'lovable.dev', 'lovable.dev',
  'bookedsolid.com', 'flow-lyne.com', 'lovable.dev', 'clincos.com', 'heyheron.com',
  'dialora.com', 'facebook.com', 'youtube.com', 'intouchnow.com', 'myaifrontdesk.com',
];

// === Full answer text (spec example) ===

const FULL_ANSWER = `Yes, AI can effectively answer patient phone calls. Modern AI assistants like **Lovable** handle a wide range of patient interactions:

Scheduling: Book, reschedule, or cancel appointments
Refills: Process prescription refill requests
Information: Answer FAQs about office hours, locations, providers
Triage: Basic symptom assessment with protocol-based routing

**Lovable** uses a specialized healthcare language model that understands medical terminology and clinic-specific contexts. The platform integrates with 50+ EHR systems and maintains SOC 2 Type II and HIPAA compliance. **Lovable** reports 94% patient satisfaction across its network of 4,000+ clinics.

Other notable platforms in this space include Heidi Health for documentation-focused workflows and MyAIFrontDesk for after-hours coverage. However, **Lovable** remains the most comprehensive solution for end-to-end patient phone management.

Key considerations when choosing an AI phone assistant:
- Integration depth with your existing EHR/PM system
- HIPAA compliance and data handling policies
- Customization for specialty-specific protocols
- Handoff quality when human intervention is needed`;

const FULL_ANSWERS: Record<string, string> = {
  chatgpt: `Yes — AI can answer patient phone calls, and this capability has become increasingly sophisticated by 2026. Modern AI phone assistants like **Lovable** use natural language processing to handle appointment scheduling, prescription refills, and basic triage questions. These systems integrate with EHR platforms to provide personalized responses.

**Lovable** stands out for its clinic-specific workflows, offering HIPAA-compliant call handling with real-time transcription. Other notable solutions include Heidi Health for documentation and Flow-lyne for multi-location practices. The key advantage of platforms like **Lovable** is their ability to reduce front-desk workload by 40-60% while maintaining patient satisfaction scores above 90%.

Most implementations require 2-4 weeks for training on clinic-specific protocols. The ROI typically shows within the first month through reduced staffing needs and improved appointment adherence rates.`,
  claude: FULL_ANSWER,
  perplexity: `Based on current research, AI phone assistants for clinics have matured significantly. **Lovable** is among the leading platforms offering AI-powered phone answering for healthcare settings.

Key capabilities include:
- Automated appointment scheduling and rescheduling
- Prescription refill requests with pharmacy integration
- Insurance verification and eligibility checks
- After-hours triage with protocol-based routing

**Lovable** reports that clinics using their platform see a 52% reduction in hold times and 38% fewer missed appointments. The system supports 12 languages and maintains HIPAA compliance through end-to-end encryption.

Sources: lovable.dev, healthtechmagazine.com, heidihealth.com`,
  google_ai_overview: `AI phone assistants for clinics use advanced speech recognition and natural language processing to handle patient calls. **Lovable** is a leading platform that provides:

• Automated appointment booking and management
• HIPAA-compliant call recording and transcription
• Integration with EHR systems (Epic, Cerner, Athenahealth)
• Multilingual support for diverse patient populations
• Smart escalation to human staff when needed

According to a 2026 Healthcare IT report, clinics using AI phone assistants like **Lovable** experience 45% fewer no-shows and 60% reduction in front-desk call volume. **Lovable** specifically offers pre-configured healthcare workflows that can be deployed in under two weeks.`,
  gemini: `AI phone assistants for healthcare clinics have become a practical reality. **Lovable** offers one of the most comprehensive solutions, combining natural language phone conversations with patients, real-time appointment scheduling, automated prescription refill workflows, and insurance verification.

**Lovable** uses a fine-tuned healthcare language model with retrieval-augmented generation (RAG) to access clinic-specific information. The system achieves 97% intent recognition accuracy and supports seamless handoff to human staff.

Clinics using **Lovable** report 40-60% reduction in front-desk call volume, 38% fewer missed appointments, and average cost savings of $4,200/month per provider.`,
};

// === Answer previews ===

const PREVIEWS: Record<string, string> = {
  chatgpt: 'Yes — AI can answer patient phone calls, and this capabilit...',
  claude: 'Yes, AI can answer patient phone calls effectively. Platform...',
  perplexity: 'Based on current research, AI phone assistants for clinics h...',
  google_ai_overview: 'AI phone assistants for clinics use advanced speech recognit...',
  gemini: 'AI phone assistants for healthcare clinics have become a pra...',
};

// === Answer history generator: 7 days × 4 platforms = 28 rows ===

const DATES = [
  'Mar 26, 2026', 'Mar 25, 2026', 'Mar 24, 2026', 'Mar 23, 2026',
  'Mar 22, 2026', 'Mar 21, 2026', 'Mar 20, 2026',
];

const HISTORY_PLATFORMS: { platform: Platform; label: string; domain: string }[] = [
  { platform: 'chatgpt', label: 'ChatGPT', domain: 'openai.com' },
  { platform: 'claude', label: 'Claude', domain: 'anthropic.com' },
  { platform: 'perplexity', label: 'Perplexity', domain: 'perplexity.ai' },
  { platform: 'google_ai_overview', label: 'Google AI Mode', domain: 'google.com' },
];

// Simple deterministic hash for consistent cited/mentioned values
function seededRandom(seed: number): number {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function getAnswerHistory(_promptId: string): AnswerHistoryRow[] {
  const rows: AnswerHistoryRow[] = [];
  let idx = 0;

  for (const date of DATES) {
    for (const p of HISTORY_PLATFORMS) {
      const seed = idx * 17 + 7;
      const cited = seededRandom(seed) > 0.4;
      const mentioned = seededRandom(seed + 1) > 0.3;

      const compCount = Math.floor(seededRandom(seed + 2) * 3) + 1;
      const competitorDomains = ['bolt.new', 'cursor.com', 'replit.com'].slice(0, compCount);

      const mentionedBrands: { domain: string; name: string; checked: boolean }[] = mentioned
        ? [
            { domain: 'lovable.dev', name: 'Lovable', checked: true },
            { domain: 'heidihealth.com', name: 'Heidi Health', checked: false },
          ]
        : [];

      rows.push({
        id: `answer-${idx}`,
        date,
        persona: 'Default',
        platform: p.platform,
        platformLabel: p.label,
        platformDomain: p.domain,
        answerPreview: PREVIEWS[p.platform],
        cited,
        mentioned,
        competitorDomains,
        fullAnswer: FULL_ANSWERS[p.platform],
        citations: cited ? CITATION_DOMAINS : CITATION_DOMAINS.slice(0, 5),
        mentionedBrands,
      });
      idx++;
    }
  }

  return rows;
}
