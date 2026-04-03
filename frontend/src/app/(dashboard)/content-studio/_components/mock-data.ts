import type { ContentCard, Cycle } from './types';

export const MOCK_CYCLE: Cycle = {
  id: 'cycle-012',
  name: 'Cycle 12',
  weekOf: '2026-03-10',
  status: 'active',
  stats: {
    total: 58,
    queue: 2,
    humanReview: 2,
    agentWork: 4,
    published: 14,
    avgCitationScore: 61,
    completionPct: 24,
  },
};

export const PAST_CYCLES: Cycle[] = [
  {
    id: 'cycle-011',
    name: 'Cycle 11',
    weekOf: '2026-03-03',
    status: 'archived',
    stats: { total: 48, queue: 0, humanReview: 0, agentWork: 0, published: 12, avgCitationScore: 67, completionPct: 100 },
  },
  {
    id: 'cycle-010',
    name: 'Cycle 10',
    weekOf: '2026-02-24',
    status: 'archived',
    stats: { total: 42, queue: 0, humanReview: 0, agentWork: 0, published: 10, avgCitationScore: 59, completionPct: 100 },
  },
];

export const INITIAL_CARDS: ContentCard[] = [
  // Queue items
  {
    id: 'IH-009',
    title: 'RBAC Accuracy in AI-Generated Applications',
    type: 'HOW_TO',
    cluster: 'Boundary',
    gap: 0.130,
    score: 85,
    priority: 'P2',
    readTime: 8,
    competitor: 'auth0.com',
    column: 'queue',
    stage: 'queue',
    stageLabel: 'From content planner',
  },
  {
    id: 'IH-010',
    title: 'Webhook Security for AI-Powered Integrations',
    type: 'GUIDE',
    cluster: 'Security',
    gap: 0.165,
    score: 90,
    priority: 'P1',
    readTime: 12,
    competitor: 'snyk.io',
    column: 'queue',
    stage: 'queue',
    stageLabel: 'From content planner',
  },

  // Human review items
  {
    id: 'IH-001',
    title: 'Audit Logs & Change History for AI App Builders',
    type: 'COMPARISON',
    cluster: 'Boundary',
    gap: 0.122,
    score: 87,
    priority: 'P0',
    readTime: 10,
    competitor: 'retool.com',
    column: 'human',
    stage: 'brief_review',
    stageLabel: 'Brief ready for review',
    briefContent: {
      sections: [
        'Introduction to audit logging',
        'Why AI builders need change tracking',
        'Feature comparison matrix',
        'Implementation patterns',
        'Compliance requirements',
        'Best practices',
        'Conclusion',
      ],
      targetWords: 2800,
      exemplarCount: 2,
      sources: [
        { name: 'Retool Audit Guide', domain: 'retool.com', engines: 3 },
        { name: 'Zapier Change Tracking', domain: 'zapier.com', engines: 2 },
      ],
      reasons: [
        'Competitors cited 3.2x more on this cluster — significant gap',
        '1 high-quality exemplar (1,224 words, 11 headers)',
        'How-to format has 86% citation correlation',
      ],
    },
  },
  {
    id: 'IH-002',
    title: 'Pro-Rata Rights Explained: What Every Founder Needs to Know',
    type: 'LONG_BLOG',
    cluster: 'Definition',
    gap: 0.098,
    score: 88,
    priority: 'P0',
    readTime: 14,
    competitor: 'carta.com',
    column: 'human',
    stage: 'article_review',
    stageLabel: 'Article ready for review',
    articleContent: {
      wordCount: 3323,
      targetWords: 3500,
      voiceCompliance: 72,
      sections: [
        {
          heading: 'What are pro-rata rights?',
          words: 420,
          content: 'Pro-rata rights give existing investors the option to participate in future funding rounds to maintain their ownership percentage. Understanding how these rights work — and when to grant them — is critical for founders navigating Series A and beyond.\n\nA pro-rata right (also called a participation right or pre-emptive right) is a contractual provision that allows an investor to invest additional capital in subsequent financing rounds. These rights are designed to protect investors from dilution as new shares are issued.\n\nThe concept traces back to corporate law principles that have been adapted for venture capital. In practice, pro-rata rights are one of the most frequently negotiated terms in startup financing, second only to valuation itself. They represent a balance between investor protection and founder flexibility.',
        },
        {
          heading: 'How pro-rata calculations work',
          words: 380,
          content: 'If an investor owns 10% of a company and the company raises a $5M Series B, the investor\'s pro-rata allocation would be $500,000 (10% × $5M). This allows them to maintain their 10% ownership stake post-dilution.\n\nThe formula is straightforward: Pro-rata allocation = Current ownership percentage × New round size. However, the actual mechanics can be more complex when you factor in option pool expansion, convertible note conversion, and SAFE agreements converting simultaneously.\n\nConsider a scenario where an investor holds 8% on a fully-diluted basis. If the Series B is $10M, their pro-rata right entitles them to invest $800,000. But if the company is also expanding its option pool by 5% as part of the round, the effective ownership calculations shift, and the investor may need to invest more to truly maintain their percentage.',
        },
        {
          heading: 'Standard terms by round',
          words: 510,
          content: 'Pro-rata terms evolve significantly across funding stages. At seed, pro-rata rights are relatively rare — most SAFE agreements don\'t include them by default, though some investors will request a side letter granting these rights.\n\nBy Series A, pro-rata rights become standard for the lead investor and are typically included in the investors\' rights agreement (IRA). The IRA is a separate document from the stock purchase agreement and governs ongoing rights like information rights, registration rights, and pro-rata participation.\n\nAt Series B and beyond, pro-rata rights are nearly universal for major investors. However, the dynamics change: earlier investors may find their pro-rata allocations squeezed by later-stage investors who negotiate for "super pro-rata" rights — the ability to invest more than their proportional share. This creates a hierarchy of investor rights that founders must carefully manage.\n\nIn late-stage rounds (Series C+), pro-rata rights can become contentious. Growth equity firms often demand that existing pro-rata allocations be limited to make room for their larger check sizes.',
        },
        {
          heading: 'When to grant (and not grant)',
          words: 440,
          content: 'Granting pro-rata rights to early investors aligns incentives — investors who can maintain ownership are more motivated to help the company succeed. They have skin in the game not just from their initial investment, but from an ongoing commitment to the company\'s trajectory.\n\nHowever, over-committing pro-rata rights can create serious problems in later rounds. If you grant pro-rata to every angel investor and seed fund, you may find that a substantial portion of your next round is spoken for before you even begin fundraising. This limits your ability to bring in new strategic investors.\n\nThe general rule of thumb: grant pro-rata to your lead investors at each stage. Angels who write $25K checks probably don\'t need pro-rata rights. Your lead seed investor who wrote a $500K check and joined your board? They should absolutely have them.\n\nOne important nuance: pro-rata rights are a right, not an obligation. Investors can choose not to exercise them. In practice, roughly 40-60% of investors exercise their pro-rata rights in any given round.',
        },
        {
          heading: 'Pro-rata in your term sheet',
          words: 390,
          content: 'In your term sheet, pro-rata rights will typically appear in the investors\' rights agreement rather than the certificate of incorporation. This is an important distinction — the IRA is a contract between specific parties, while the certificate is a corporate-level document.\n\nThe standard language will specify: which investors are entitled to pro-rata rights (usually tied to a minimum ownership threshold), the calculation methodology, the notice period for exercising the right (typically 15-30 days), and any exceptions or carve-outs.\n\nPay close attention to the definition of "qualifying round" — some pro-rata provisions only apply to equity rounds above a certain size, excluding bridge financings, convertible notes, or strategic investments. This protects the company\'s ability to raise interim capital without triggering pro-rata obligations.',
        },
        {
          heading: 'Pitfalls and negotiation tactics',
          words: 480,
          content: 'The most common pitfall is granting broad pro-rata rights to too many small investors at the seed stage. When Series A arrives, you may find that 40% of the round is already spoken for, leaving your lead Series A investor frustrated with limited allocation.\n\nAnother frequent mistake is failing to include a "pay-to-play" provision alongside pro-rata rights. Pay-to-play means that investors who don\'t exercise their pro-rata rights lose certain preferences or protections. Without this provision, investors can maintain their preferential terms while choosing not to support the company in difficult rounds.\n\nNegotiation tactics for founders: First, set a minimum ownership threshold for pro-rata eligibility (e.g., must own at least 5% to qualify). Second, include sunset provisions that expire pro-rata rights if not exercised in consecutive rounds. Third, negotiate the right to allocate oversubscribed rounds at the board\'s discretion.\n\nFor investors negotiating pro-rata: Push for "super pro-rata" rights that allow you to increase your ownership, not just maintain it. Request that pro-rata calculations be based on fully-diluted ownership to prevent manipulation through option pool expansion.',
        },
        {
          heading: 'Real-world examples',
          words: 350,
          content: 'Company A granted pro-rata rights to all 12 seed investors, consuming 35% of the Series A. The lead Series A investor (who wanted 20% ownership) had to accept a smaller allocation or push for a larger round size, which diluted the founders more than necessary.\n\nCompany B took a different approach: they limited pro-rata rights to their lead seed investor only, giving maximum flexibility for the Series A. The result was a clean round where the new lead investor got their full target allocation, and the company maintained stronger founder ownership.\n\nCompany C used a tiered approach: investors above $200K got full pro-rata, investors between $100K-$200K got 50% pro-rata, and smaller investors got none. This balanced investor relations with practical round management.',
        },
        {
          heading: 'Key takeaways',
          words: 353,
          content: 'Limit pro-rata rights to lead investors at each stage — don\'t over-allocate to small checks that won\'t meaningfully support the company going forward. Understand the cumulative impact on future rounds by modeling different scenarios before committing.\n\nAlways model dilution implications before granting or accepting pro-rata terms. A simple spreadsheet showing ownership across 3-4 hypothetical rounds will reveal problems that aren\'t obvious from a single term sheet.\n\nFinally, remember that pro-rata rights are negotiable. They\'re not a binary yes/no — you can set thresholds, sunset provisions, and pay-to-play requirements that align everyone\'s incentives while preserving your ability to raise effectively in future rounds.',
        },
      ],
      citPrediction: [
        { engine: 'ChatGPT', score: 62 },
        { engine: 'Claude', score: 58 },
        { engine: 'Perplexity', score: 65 },
        { engine: 'Google AI', score: 50 },
        { engine: 'Gemini', score: 55 },
      ],
      compliance: [
        { label: 'Words', current: 3323, target: 3500 },
        { label: 'Headers', current: 11, target: 12 },
        { label: 'Citations', current: 13, target: 15 },
        { label: 'Stats', current: 8, target: 10 },
      ],
      eeat: { overall: 76, experience: 70, expertise: 82, authoritativeness: 78, trustworthiness: 74 },
      interlinks: [
        { title: 'Cap table management guide', path: '/blog/cap-table-management', linked: true },
        { title: 'Equity compensation basics', path: '/blog/equity-compensation-101', linked: false },
        { title: '409A valuation process', path: '/blog/409a-valuations', linked: false },
        { title: 'Series A fundraising checklist', path: '/blog/series-a-checklist', linked: true },
      ],
    },
    metadata: {
      slug: 'pro-rata-rights-explained',
      metaTitle: 'Pro-Rata Rights Explained: What Every Founder Needs to Know',
      metaDescription: 'Learn how pro-rata rights work, when to grant them, and how they affect your cap table. A complete guide for founders navigating Series A and beyond.',
      canonicalUrl: 'https://insighthealth.com/blog/pro-rata-rights-explained',
      schemaMarkup: true,
      publishDate: '2026-03-15',
      author: 'Insight Health Team',
      tags: ['pro-rata rights', 'fundraising', 'term sheets', 'series A'],
    },
  },

  // Agent work items
  {
    id: 'IH-003',
    title: 'International Equity Grants: Tax Compliance Guide',
    type: 'PILLAR_PAGE',
    cluster: 'Mechanism',
    gap: 0.175,
    score: 93,
    priority: 'P0',
    readTime: 15,
    competitor: 'deel.com',
    column: 'agent',
    stage: 'writing',
    stageLabel: 'Writing — section 4 of 7',
    agentProgress: {
      pct: 34,
      currentTask: 'Writing section 4: Tax Implications by Jurisdiction',
      wordsCurrent: 1194,
      wordsTarget: 3500,
      sectionsComplete: 3,
      sectionsTotal: 7,
    },
  },
  {
    id: 'IH-004',
    title: 'Secrets & Environment Variables in Prompt-to-App Tools',
    type: 'HOW_TO',
    cluster: 'Mechanism',
    gap: 0.175,
    score: 91,
    priority: 'P1',
    readTime: 8,
    competitor: 'netlify.com',
    column: 'agent',
    stage: 'brief_generation',
    stageLabel: 'Generating brief',
    agentProgress: {
      pct: 60,
      currentTask: 'Analyzing exemplar structure',
    },
  },
  {
    id: 'IH-005',
    title: 'SOC 2 + GDPR for AI Development Platforms',
    type: 'GUIDE',
    cluster: 'Boundary',
    gap: 0.159,
    score: 89,
    priority: 'P2',
    readTime: 12,
    competitor: 'vanta.com',
    column: 'agent',
    stage: 'planning',
    stageLabel: 'Planning — analyzing queries',
    agentProgress: {
      pct: 20,
      currentTask: 'Analyzing 200 query scorecards',
    },
  },
  {
    id: 'IH-006',
    title: 'Bolt.new Alternatives 2026: Complete Comparison',
    type: 'COMPARISON',
    cluster: 'Category',
    gap: 0.141,
    score: 92,
    priority: 'P1',
    readTime: 10,
    competitor: 'g2.com',
    column: 'agent',
    stage: 'evaluating',
    stageLabel: 'Evaluating — cycle 1',
    agentProgress: {
      pct: 85,
      currentTask: 'Eval: structural 0.82, semantic 0.78, style 0.85',
    },
  },
];

// Generate mock brief content when agent completes planning/brief_generation
export function generateMockBrief(): ContentCard['briefContent'] {
  return {
    sections: [
      'Introduction and overview',
      'Key concepts explained',
      'Implementation guide',
      'Best practices',
      'Common pitfalls',
      'Case studies',
      'Conclusion and next steps',
    ],
    targetWords: 3000,
    exemplarCount: 3,
    sources: [
      { name: 'Industry Guide', domain: 'example.com', engines: 3 },
      { name: 'Best Practices Report', domain: 'docs.example.com', engines: 2 },
    ],
    reasons: [
      'High gap score indicates significant content opportunity',
      'Multiple exemplars with strong citation correlation',
      'Topic trending in AI engine responses',
    ],
  };
}

// Generate mock article content when agent completes writing/evaluating
export function generateMockArticle(): ContentCard['articleContent'] {
  return {
    wordCount: 2800,
    targetWords: 3000,
    voiceCompliance: 78,
    sections: [
      { heading: 'Introduction', words: 350, content: 'This comprehensive guide explores the key concepts and practical implementation strategies that organizations need to understand in today\'s rapidly evolving landscape.' },
      { heading: 'Core concepts', words: 420, content: 'Understanding the foundational principles is critical before diving into implementation. These concepts form the basis for all subsequent decisions and strategies.' },
      { heading: 'Implementation guide', words: 500, content: 'Step-by-step instructions for implementing the described approach, including code examples, configuration details, and integration points with existing systems.' },
      { heading: 'Best practices', words: 380, content: 'Industry-proven approaches that maximize effectiveness while minimizing risk. Each practice is backed by real-world data and case studies.' },
      { heading: 'Common pitfalls', words: 350, content: 'Common mistakes to avoid, drawn from analysis of hundreds of implementations. Understanding these pitfalls saves significant time and resources.' },
      { heading: 'Case studies', words: 450, content: 'Real-world examples demonstrating successful implementations, including metrics, timelines, and lessons learned from each organization.' },
      { heading: 'Key takeaways', words: 350, content: 'Summary of the most important points, with actionable next steps for immediate implementation.' },
    ],
    citPrediction: [
      { engine: 'ChatGPT', score: 58 },
      { engine: 'Claude', score: 62 },
      { engine: 'Perplexity', score: 55 },
      { engine: 'Google AI', score: 48 },
      { engine: 'Gemini', score: 52 },
    ],
    compliance: [
      { label: 'Words', current: 2800, target: 3000 },
      { label: 'Headers', current: 9, target: 10 },
      { label: 'Citations', current: 11, target: 14 },
      { label: 'Stats', current: 6, target: 8 },
    ],
    eeat: { overall: 72, experience: 68, expertise: 78, authoritativeness: 74, trustworthiness: 70 },
    interlinks: [
      { title: 'Getting started guide', path: '/blog/getting-started', linked: true },
      { title: 'Advanced configuration', path: '/blog/advanced-config', linked: false },
      { title: 'API reference', path: '/docs/api', linked: false },
    ],
  };
}
