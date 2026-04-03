// Brand Presence — Mock Data Generator
// 28 days of realistic time-series data with sine waves + noise

export interface DayData {
  date: string;
  dateShort: string;
  presenceScore: number;
  sov: number;
  citations: number;
  mentions: number;
  position: number;
  chatgpt: number;
  claude: number;
  perplexity: number;
  google: number;
  gemini: number;
  positive: number;
  neutral: number;
  negative: number;
  boltSov: number;
  cursorSov: number;
  replitSov: number;
  v0Sov: number;
  emergentSov: number;
  // Competitor citations (daily)
  boltCitations: number;
  cursorCitations: number;
  replitCitations: number;
  v0Citations: number;
  emergentCitations: number;
  // Competitor mentions (daily)
  boltMentions: number;
  cursorMentions: number;
  replitMentions: number;
  v0Mentions: number;
  emergentMentions: number;
  // Competitor avg position
  boltPosition: number;
  cursorPosition: number;
  replitPosition: number;
  v0Position: number;
  emergentPosition: number;
  // Competitor presence score
  boltPresence: number;
  cursorPresence: number;
  replitPresence: number;
  v0Presence: number;
  emergentPresence: number;
  // Additional competitors
  retoolSov: number; retoolCitations: number; retoolMentions: number; retoolPosition: number; retoolPresence: number;
  webflowSov: number; webflowCitations: number; webflowMentions: number; webflowPosition: number; webflowPresence: number;
  framerSov: number; framerCitations: number; framerMentions: number; framerPosition: number; framerPresence: number;
  bubbleSov: number; bubbleCitations: number; bubbleMentions: number; bubblePosition: number; bubblePresence: number;
  glideSov: number; glideCitations: number; glideMentions: number; glidePosition: number; glidePresence: number;
  softrSov: number; softrCitations: number; softrMentions: number; softrPosition: number; softrPresence: number;
  appsmithSov: number; appsmithCitations: number; appsmithMentions: number; appsmithPosition: number; appsmithPresence: number;
  streamlitSov: number; streamlitCitations: number; streamlitMentions: number; streamlitPosition: number; streamlitPresence: number;
}

function lerp(start: number, end: number, t: number): number {
  return start + (end - start) * t;
}

function noise(seed: number): number {
  const x = Math.sin(seed * 12.9898 + seed * 78.233) * 43758.5453;
  return x - Math.floor(x);
}

function wave(t: number, freq: number, phase: number): number {
  return Math.sin(t * freq * Math.PI * 2 + phase);
}

export function generateDayData(): DayData[] {
  const days: DayData[] = [];
  const startDate = new Date(2026, 2, 1); // Mar 1, 2026

  for (let i = 0; i < 28; i++) {
    const t = i / 27; // 0 to 1
    const d = new Date(startDate);
    d.setDate(d.getDate() + i);

    const dateStr = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    const dateShort = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

    // Noise factors
    const n1 = (noise(i * 7.1) - 0.5) * 2;
    const n2 = (noise(i * 3.3) - 0.5) * 2;
    const n3 = (noise(i * 5.7) - 0.5) * 2;

    // SOV: 8.1% → 12.4% with variation
    const sov = lerp(8.1, 12.4, t) + wave(t, 2.5, 0) * 0.8 + n1 * 0.4;

    // Citations: 22 → 32 daily
    const citations = Math.round(lerp(22, 32, t) + wave(t, 3, 1.2) * 3 + n2 * 2);

    // Mentions: 35 → 48 daily
    const mentions = Math.round(lerp(35, 48, t) + wave(t, 2.8, 0.5) * 4 + n3 * 2.5);

    // Position: 3.1 → 2.3 (lower is better)
    const position = Math.round((lerp(3.1, 2.3, t) + wave(t, 2, 2.1) * 0.2 + n1 * 0.1) * 10) / 10;

    // Platform breakdown (proportional to total citations)
    const chatgpt = Math.round(citations * (0.368 + n1 * 0.02));
    const claude = Math.round(citations * (0.212 + n2 * 0.015));
    const perplexity = Math.round(citations * (0.184 + n3 * 0.01));
    const google = Math.round(citations * (0.135 + (noise(i * 2.1) - 0.5) * 0.01));
    const gemini = Math.max(1, citations - chatgpt - claude - perplexity - google);

    // Sentiment
    const positive = Math.round(lerp(69, 74, t) + n1 * 2);
    const neutral = Math.round(lerp(24, 20, t) + n2 * 1.5);
    const negative = 100 - positive - neutral;

    // Presence Score calculation
    const sovScore = Math.min(sov / 25 * 100, 100);
    const citationRate = (citations / (citations + mentions)) * 100;
    const positionScore = Math.max(0, (5 - position) / 4 * 100);
    const sentimentScore = positive;
    const platformCount = [chatgpt, claude, perplexity, google, gemini].filter(v => v > 0).length;
    const coverageScore = (platformCount / 5) * 100;

    const presenceScore = Math.round(
      sovScore * 0.35 +
      citationRate * 0.25 +
      positionScore * 0.20 +
      sentimentScore * 0.10 +
      coverageScore * 0.10
    );

    // Competitor SOV
    const boltSov = lerp(18.5, 17.1, t) + wave(t, 1.8, 3.0) * 0.5 + (noise(i * 4.2) - 0.5) * 0.3;
    const cursorSov = lerp(11.5, 11.8, t) + wave(t, 2.2, 1.5) * 0.3 + (noise(i * 6.1) - 0.5) * 0.2;
    const replitSov = lerp(9.5, 8.8, t) + wave(t, 1.5, 0.8) * 0.4 + (noise(i * 8.3) - 0.5) * 0.3;
    const v0Sov = lerp(7.1, 7.4, t) + wave(t, 2.0, 2.5) * 0.2 + (noise(i * 9.7) - 0.5) * 0.15;
    const emergentSov = lerp(5.0, 5.3, t) + wave(t, 1.3, 4.0) * 0.15 + (noise(i * 11.2) - 0.5) * 0.1;

    // Competitor daily citations
    const boltCitations = Math.round(lerp(38, 35, t) + wave(t, 1.8, 2.0) * 3 + (noise(i * 4.5) - 0.5) * 2);
    const cursorCitations = Math.round(lerp(24, 25, t) + wave(t, 2.1, 1.0) * 2 + (noise(i * 5.5) - 0.5) * 2);
    const replitCitations = Math.round(lerp(20, 18, t) + wave(t, 1.6, 0.5) * 2 + (noise(i * 7.1) - 0.5) * 1.5);
    const v0Citations = Math.round(lerp(15, 16, t) + wave(t, 1.9, 3.0) * 1.5 + (noise(i * 8.5) - 0.5) * 1);
    const emergentCitations = Math.round(lerp(10, 11, t) + wave(t, 1.4, 4.0) * 1 + (noise(i * 10.2) - 0.5) * 0.8);

    // Competitor daily mentions
    const boltMentions = Math.round(lerp(55, 52, t) + wave(t, 1.5, 1.5) * 4 + (noise(i * 3.8) - 0.5) * 3);
    const cursorMentions = Math.round(lerp(40, 42, t) + wave(t, 2.0, 2.5) * 3 + (noise(i * 5.9) - 0.5) * 2);
    const replitMentions = Math.round(lerp(32, 29, t) + wave(t, 1.7, 1.0) * 3 + (noise(i * 7.6) - 0.5) * 2);
    const v0Mentions = Math.round(lerp(25, 26, t) + wave(t, 1.8, 3.5) * 2 + (noise(i * 9.1) - 0.5) * 1.5);
    const emergentMentions = Math.round(lerp(18, 19, t) + wave(t, 1.3, 2.0) * 1.5 + (noise(i * 10.8) - 0.5) * 1);

    // Competitor avg position
    const boltPosition = Math.round((lerp(1.8, 2.0, t) + wave(t, 1.5, 1.0) * 0.15 + (noise(i * 4.1) - 0.5) * 0.1) * 10) / 10;
    const cursorPosition = Math.round((lerp(2.5, 2.4, t) + wave(t, 2.0, 2.0) * 0.12 + (noise(i * 6.5) - 0.5) * 0.08) * 10) / 10;
    const replitPosition = Math.round((lerp(3.2, 3.4, t) + wave(t, 1.6, 0.8) * 0.15 + (noise(i * 8.0) - 0.5) * 0.1) * 10) / 10;
    const v0Position = Math.round((lerp(3.5, 3.3, t) + wave(t, 1.8, 2.5) * 0.1 + (noise(i * 9.4) - 0.5) * 0.08) * 10) / 10;
    const emergentPosition = Math.round((lerp(4.0, 3.8, t) + wave(t, 1.2, 3.0) * 0.1 + (noise(i * 11.0) - 0.5) * 0.06) * 10) / 10;

    // Competitor presence scores (simplified)
    const boltPresence = Math.round(lerp(82, 79, t) + wave(t, 1.5, 2.0) * 2 + (noise(i * 4.3) - 0.5) * 1.5);
    const cursorPresence = Math.round(lerp(68, 69, t) + wave(t, 2.0, 1.5) * 1.5 + (noise(i * 6.2) - 0.5) * 1);
    const replitPresence = Math.round(lerp(61, 58, t) + wave(t, 1.6, 1.0) * 2 + (noise(i * 8.1) - 0.5) * 1.5);
    const v0Presence = Math.round(lerp(55, 56, t) + wave(t, 1.8, 2.5) * 1 + (noise(i * 9.5) - 0.5) * 0.8);
    const emergentPresence = Math.round(lerp(42, 44, t) + wave(t, 1.3, 3.5) * 1 + (noise(i * 11.1) - 0.5) * 0.6);

    // Additional competitors
    const retoolSov = lerp(4.8, 4.6, t) + wave(t, 1.4, 2.0) * 0.2 + (noise(i * 12.3) - 0.5) * 0.15;
    const webflowSov = lerp(4.2, 4.0, t) + wave(t, 1.6, 1.5) * 0.18 + (noise(i * 13.1) - 0.5) * 0.12;
    const framerSov = lerp(3.9, 4.1, t) + wave(t, 1.3, 3.0) * 0.15 + (noise(i * 14.2) - 0.5) * 0.1;
    const bubbleSov = lerp(3.5, 3.3, t) + wave(t, 1.5, 2.5) * 0.12 + (noise(i * 15.0) - 0.5) * 0.08;
    const glideSov = lerp(2.8, 2.6, t) + wave(t, 1.2, 1.0) * 0.1 + (noise(i * 16.1) - 0.5) * 0.06;
    const softrSov = lerp(2.1, 2.0, t) + wave(t, 1.1, 2.0) * 0.08 + (noise(i * 17.3) - 0.5) * 0.05;
    const appsmithSov = lerp(1.7, 1.6, t) + wave(t, 1.0, 1.5) * 0.06 + (noise(i * 18.2) - 0.5) * 0.04;
    const streamlitSov = lerp(1.4, 1.5, t) + wave(t, 0.9, 3.0) * 0.05 + (noise(i * 19.0) - 0.5) * 0.03;

    const retoolCitations = Math.round(lerp(10, 9, t) + wave(t, 1.4, 2.0) * 1 + (noise(i * 12.5) - 0.5) * 0.8);
    const webflowCitations = Math.round(lerp(9, 8, t) + wave(t, 1.6, 1.5) * 0.8 + (noise(i * 13.3) - 0.5) * 0.6);
    const framerCitations = Math.round(lerp(8, 9, t) + wave(t, 1.3, 3.0) * 0.7 + (noise(i * 14.4) - 0.5) * 0.5);
    const bubbleCitations = Math.round(lerp(7, 7, t) + wave(t, 1.5, 2.5) * 0.6 + (noise(i * 15.2) - 0.5) * 0.4);
    const glideCitations = Math.round(lerp(6, 5, t) + wave(t, 1.2, 1.0) * 0.5 + (noise(i * 16.3) - 0.5) * 0.3);
    const softrCitations = Math.round(lerp(4, 4, t) + wave(t, 1.1, 2.0) * 0.4 + (noise(i * 17.5) - 0.5) * 0.3);
    const appsmithCitations = Math.round(lerp(3, 3, t) + wave(t, 1.0, 1.5) * 0.3 + (noise(i * 18.4) - 0.5) * 0.2);
    const streamlitCitations = Math.round(lerp(3, 3, t) + wave(t, 0.9, 3.0) * 0.2 + (noise(i * 19.2) - 0.5) * 0.2);

    const retoolMentions = Math.round(lerp(16, 15, t) + (noise(i * 12.7) - 0.5) * 1.5);
    const webflowMentions = Math.round(lerp(14, 13, t) + (noise(i * 13.5) - 0.5) * 1.2);
    const framerMentions = Math.round(lerp(13, 14, t) + (noise(i * 14.6) - 0.5) * 1);
    const bubbleMentions = Math.round(lerp(12, 11, t) + (noise(i * 15.4) - 0.5) * 0.8);
    const glideMentions = Math.round(lerp(10, 9, t) + (noise(i * 16.5) - 0.5) * 0.6);
    const softrMentions = Math.round(lerp(8, 7, t) + (noise(i * 17.7) - 0.5) * 0.5);
    const appsmithMentions = Math.round(lerp(6, 6, t) + (noise(i * 18.6) - 0.5) * 0.4);
    const streamlitMentions = Math.round(lerp(5, 5, t) + (noise(i * 19.4) - 0.5) * 0.3);

    const retoolPosition = Math.round((lerp(3.8, 3.9, t) + (noise(i * 12.9) - 0.5) * 0.1) * 10) / 10;
    const webflowPosition = Math.round((lerp(4.0, 4.1, t) + (noise(i * 13.7) - 0.5) * 0.08) * 10) / 10;
    const framerPosition = Math.round((lerp(3.7, 3.6, t) + (noise(i * 14.8) - 0.5) * 0.08) * 10) / 10;
    const bubblePosition = Math.round((lerp(4.2, 4.3, t) + (noise(i * 15.6) - 0.5) * 0.06) * 10) / 10;
    const glidePosition = Math.round((lerp(4.3, 4.4, t) + (noise(i * 16.7) - 0.5) * 0.06) * 10) / 10;
    const softrPosition = Math.round((lerp(4.5, 4.5, t) + (noise(i * 17.9) - 0.5) * 0.05) * 10) / 10;
    const appsmithPosition = Math.round((lerp(4.6, 4.6, t) + (noise(i * 18.8) - 0.5) * 0.04) * 10) / 10;
    const streamlitPosition = Math.round((lerp(4.4, 4.3, t) + (noise(i * 19.6) - 0.5) * 0.04) * 10) / 10;

    const retoolPresence = Math.round(lerp(38, 37, t) + wave(t, 1.4, 2.0) * 1 + (noise(i * 12.4) - 0.5) * 0.8);
    const webflowPresence = Math.round(lerp(35, 34, t) + wave(t, 1.6, 1.5) * 0.8 + (noise(i * 13.4) - 0.5) * 0.6);
    const framerPresence = Math.round(lerp(33, 34, t) + wave(t, 1.3, 3.0) * 0.7 + (noise(i * 14.5) - 0.5) * 0.5);
    const bubblePresence = Math.round(lerp(30, 29, t) + wave(t, 1.5, 2.5) * 0.6 + (noise(i * 15.3) - 0.5) * 0.4);
    const glidePresence = Math.round(lerp(25, 24, t) + wave(t, 1.2, 1.0) * 0.5 + (noise(i * 16.4) - 0.5) * 0.3);
    const softrPresence = Math.round(lerp(20, 19, t) + wave(t, 1.1, 2.0) * 0.4 + (noise(i * 17.6) - 0.5) * 0.3);
    const appsmithPresence = Math.round(lerp(17, 16, t) + wave(t, 1.0, 1.5) * 0.3 + (noise(i * 18.5) - 0.5) * 0.2);
    const streamlitPresence = Math.round(lerp(15, 15, t) + wave(t, 0.9, 3.0) * 0.2 + (noise(i * 19.3) - 0.5) * 0.2);

    days.push({
      date: dateStr,
      dateShort,
      presenceScore: Math.max(0, Math.min(100, presenceScore)),
      sov: Math.round(sov * 10) / 10,
      citations: Math.max(0, citations),
      mentions: Math.max(0, mentions),
      position: Math.max(1, Math.min(5, position)),
      chatgpt: Math.max(0, chatgpt),
      claude: Math.max(0, claude),
      perplexity: Math.max(0, perplexity),
      google: Math.max(0, google),
      gemini: Math.max(0, gemini),
      positive: Math.max(0, positive),
      neutral: Math.max(0, neutral),
      negative: Math.max(0, Math.min(100, negative)),
      boltSov: Math.round(boltSov * 10) / 10,
      cursorSov: Math.round(cursorSov * 10) / 10,
      replitSov: Math.round(replitSov * 10) / 10,
      v0Sov: Math.round(v0Sov * 10) / 10,
      emergentSov: Math.round(emergentSov * 10) / 10,
      boltCitations: Math.max(0, boltCitations),
      cursorCitations: Math.max(0, cursorCitations),
      replitCitations: Math.max(0, replitCitations),
      v0Citations: Math.max(0, v0Citations),
      emergentCitations: Math.max(0, emergentCitations),
      boltMentions: Math.max(0, boltMentions),
      cursorMentions: Math.max(0, cursorMentions),
      replitMentions: Math.max(0, replitMentions),
      v0Mentions: Math.max(0, v0Mentions),
      emergentMentions: Math.max(0, emergentMentions),
      boltPosition: Math.max(1, Math.min(5, boltPosition)),
      cursorPosition: Math.max(1, Math.min(5, cursorPosition)),
      replitPosition: Math.max(1, Math.min(5, replitPosition)),
      v0Position: Math.max(1, Math.min(5, v0Position)),
      emergentPosition: Math.max(1, Math.min(5, emergentPosition)),
      boltPresence: Math.max(0, Math.min(100, boltPresence)),
      cursorPresence: Math.max(0, Math.min(100, cursorPresence)),
      replitPresence: Math.max(0, Math.min(100, replitPresence)),
      v0Presence: Math.max(0, Math.min(100, v0Presence)),
      emergentPresence: Math.max(0, Math.min(100, emergentPresence)),
      retoolSov: Math.round(retoolSov * 10) / 10, retoolCitations: Math.max(0, retoolCitations), retoolMentions: Math.max(0, retoolMentions), retoolPosition: Math.max(1, Math.min(5, retoolPosition)), retoolPresence: Math.max(0, Math.min(100, retoolPresence)),
      webflowSov: Math.round(webflowSov * 10) / 10, webflowCitations: Math.max(0, webflowCitations), webflowMentions: Math.max(0, webflowMentions), webflowPosition: Math.max(1, Math.min(5, webflowPosition)), webflowPresence: Math.max(0, Math.min(100, webflowPresence)),
      framerSov: Math.round(framerSov * 10) / 10, framerCitations: Math.max(0, framerCitations), framerMentions: Math.max(0, framerMentions), framerPosition: Math.max(1, Math.min(5, framerPosition)), framerPresence: Math.max(0, Math.min(100, framerPresence)),
      bubbleSov: Math.round(bubbleSov * 10) / 10, bubbleCitations: Math.max(0, bubbleCitations), bubbleMentions: Math.max(0, bubbleMentions), bubblePosition: Math.max(1, Math.min(5, bubblePosition)), bubblePresence: Math.max(0, Math.min(100, bubblePresence)),
      glideSov: Math.round(glideSov * 10) / 10, glideCitations: Math.max(0, glideCitations), glideMentions: Math.max(0, glideMentions), glidePosition: Math.max(1, Math.min(5, glidePosition)), glidePresence: Math.max(0, Math.min(100, glidePresence)),
      softrSov: Math.round(softrSov * 10) / 10, softrCitations: Math.max(0, softrCitations), softrMentions: Math.max(0, softrMentions), softrPosition: Math.max(1, Math.min(5, softrPosition)), softrPresence: Math.max(0, Math.min(100, softrPresence)),
      appsmithSov: Math.round(appsmithSov * 10) / 10, appsmithCitations: Math.max(0, appsmithCitations), appsmithMentions: Math.max(0, appsmithMentions), appsmithPosition: Math.max(1, Math.min(5, appsmithPosition)), appsmithPresence: Math.max(0, Math.min(100, appsmithPresence)),
      streamlitSov: Math.round(streamlitSov * 10) / 10, streamlitCitations: Math.max(0, streamlitCitations), streamlitMentions: Math.max(0, streamlitMentions), streamlitPosition: Math.max(1, Math.min(5, streamlitPosition)), streamlitPresence: Math.max(0, Math.min(100, streamlitPresence)),
    });
  }

  return days;
}

export interface Competitor {
  domain: string;
  name: string;
  isYou?: boolean;
  keys: Record<ViewType, keyof DayData>;
}

export const COMPETITORS: Competitor[] = [
  { domain: 'bolt.new', name: 'Bolt.new', keys: { presenceScore: 'boltPresence', sov: 'boltSov', citations: 'boltCitations', mentions: 'boltMentions', position: 'boltPosition' } },
  { domain: 'lovable.dev', name: 'Lovable', isYou: true, keys: { presenceScore: 'presenceScore', sov: 'sov', citations: 'citations', mentions: 'mentions', position: 'position' } },
  { domain: 'cursor.com', name: 'Cursor', keys: { presenceScore: 'cursorPresence', sov: 'cursorSov', citations: 'cursorCitations', mentions: 'cursorMentions', position: 'cursorPosition' } },
  { domain: 'replit.com', name: 'Replit', keys: { presenceScore: 'replitPresence', sov: 'replitSov', citations: 'replitCitations', mentions: 'replitMentions', position: 'replitPosition' } },
  { domain: 'v0.dev', name: 'V0.dev', keys: { presenceScore: 'v0Presence', sov: 'v0Sov', citations: 'v0Citations', mentions: 'v0Mentions', position: 'v0Position' } },
  { domain: 'emergent.sh', name: 'Emergent', keys: { presenceScore: 'emergentPresence', sov: 'emergentSov', citations: 'emergentCitations', mentions: 'emergentMentions', position: 'emergentPosition' } },
  { domain: 'retool.com', name: 'Retool', keys: { presenceScore: 'retoolPresence', sov: 'retoolSov', citations: 'retoolCitations', mentions: 'retoolMentions', position: 'retoolPosition' } },
  { domain: 'webflow.com', name: 'Webflow', keys: { presenceScore: 'webflowPresence', sov: 'webflowSov', citations: 'webflowCitations', mentions: 'webflowMentions', position: 'webflowPosition' } },
  { domain: 'framer.com', name: 'Framer', keys: { presenceScore: 'framerPresence', sov: 'framerSov', citations: 'framerCitations', mentions: 'framerMentions', position: 'framerPosition' } },
  { domain: 'bubble.io', name: 'Bubble', keys: { presenceScore: 'bubblePresence', sov: 'bubbleSov', citations: 'bubbleCitations', mentions: 'bubbleMentions', position: 'bubblePosition' } },
  { domain: 'glide.com', name: 'Glide', keys: { presenceScore: 'glidePresence', sov: 'glideSov', citations: 'glideCitations', mentions: 'glideMentions', position: 'glidePosition' } },
  { domain: 'softr.io', name: 'Softr', keys: { presenceScore: 'softrPresence', sov: 'softrSov', citations: 'softrCitations', mentions: 'softrMentions', position: 'softrPosition' } },
  { domain: 'appsmith.com', name: 'Appsmith', keys: { presenceScore: 'appsmithPresence', sov: 'appsmithSov', citations: 'appsmithCitations', mentions: 'appsmithMentions', position: 'appsmithPosition' } },
  { domain: 'streamlit.io', name: 'Streamlit', keys: { presenceScore: 'streamlitPresence', sov: 'streamlitSov', citations: 'streamlitCitations', mentions: 'streamlitMentions', position: 'streamlitPosition' } },
];

export const PLATFORMS = [
  { key: 'chatgpt' as const, name: 'ChatGPT', domain: 'openai.com', color: '#10A37F' },
  { key: 'claude' as const, name: 'Claude', domain: 'anthropic.com', color: '#D4A574' },
  { key: 'perplexity' as const, name: 'Perplexity', domain: 'perplexity.ai', color: '#20B8CD' },
  { key: 'google' as const, name: 'Google AI', domain: 'google.com', color: '#4285F4' },
  { key: 'gemini' as const, name: 'Gemini', domain: 'gemini.google.com', color: '#8E75B2' },
];

export const CITATION_URLS = [
  { url: 'lovable.dev/blog/ai-app-builder-comparison', title: 'AI App Builder Comparison Guide', citations: 63, platforms: ['chatgpt', 'claude', 'perplexity', 'google'], cps: 0.713, velocity: 4.8, firstCited: 'Jan 14, 2026' },
  { url: 'lovable.dev/blog/lovable-vs-cursor', title: 'Lovable vs Cursor: Honest Review', citations: 38, platforms: ['chatgpt', 'perplexity', 'google'], cps: 0.654, velocity: 3.9, firstCited: 'Jan 21, 2026' },
  { url: 'lovable.dev/blog/vibe-coding-enterprise', title: 'Vibe Coding for Enterprise Teams', citations: 31, platforms: ['claude', 'perplexity', 'google'], cps: 0.649, velocity: 3.2, firstCited: 'Jan 31, 2026' },
  { url: 'lovable.dev/blog/bolt-new-alternatives', title: 'Bolt.new Alternatives in 2026', citations: 29, platforms: ['chatgpt', 'perplexity'], cps: 0.521, velocity: 1.4, firstCited: 'Feb 13, 2026' },
  { url: 'lovable.dev/blog/security-ai-apps', title: 'Security in AI-Generated Apps', citations: 24, platforms: ['claude', 'chatgpt'], cps: 0.482, velocity: 2.1, firstCited: 'Feb 7, 2026' },
  { url: 'lovable.dev/blog/non-tech-founder-guide', title: "Non-Technical Founder's Guide", citations: 22, platforms: ['chatgpt', 'claude', 'perplexity'], cps: 0.538, velocity: 2.9, firstCited: 'Feb 19, 2026' },
  { url: 'lovable.dev/docs/getting-started', title: 'Getting Started Guide', citations: 19, platforms: ['chatgpt', 'claude'], cps: 0.521, velocity: 1.5, firstCited: 'Jan 9, 2026' },
  { url: 'lovable.dev/blog/rbac-ai-apps', title: 'RBAC in AI-Generated Applications', citations: 18, platforms: ['claude', 'perplexity'], cps: 0.459, velocity: 0.8, firstCited: 'Feb 24, 2026' },
];

export type ViewType = 'presenceScore' | 'sov' | 'citations' | 'mentions' | 'position';

export interface ViewConfig {
  key: ViewType;
  label: string;
  dataKey: keyof DayData;
  color: string;
  suffix: string;
  format: (v: number) => string;
  deltaFormat: (current: number, previous: number) => string;
  leaderboardLabel: string;
}

export const VIEW_CONFIGS: ViewConfig[] = [
  {
    key: 'presenceScore',
    label: 'Presence Score',
    dataKey: 'presenceScore',
    color: 'var(--accent)',
    suffix: '',
    format: (v) => String(Math.round(v)),
    deltaFormat: (c, p) => {
      const d = Math.round(c - p);
      return d >= 0 ? `+${d} this month` : `${d} this month`;
    },
    leaderboardLabel: 'Presence Score Ranking',
  },
  {
    key: 'sov',
    label: 'Share of Voice',
    dataKey: 'sov',
    color: 'var(--accent)',
    suffix: '%',
    format: (v) => `${v.toFixed(1)}%`,
    deltaFormat: (c, p) => {
      const d = (c - p).toFixed(1);
      return Number(d) >= 0 ? `+${d}pp` : `${d}pp`;
    },
    leaderboardLabel: 'Share of Voice Ranking',
  },
  {
    key: 'citations',
    label: 'Citations',
    dataKey: 'citations',
    color: 'var(--success)',
    suffix: '',
    format: (v) => String(Math.round(v)),
    deltaFormat: (c, p) => {
      const d = Math.round(c - p);
      return d >= 0 ? `+${d} this period` : `${d} this period`;
    },
    leaderboardLabel: 'Citation Count Ranking',
  },
  {
    key: 'mentions',
    label: 'Mentions',
    dataKey: 'mentions',
    color: '#8B5CF6',
    suffix: '',
    format: (v) => v.toLocaleString(),
    deltaFormat: (c, p) => {
      const d = Math.round(c - p);
      return d >= 0 ? `+${d} this period` : `${d} this period`;
    },
    leaderboardLabel: 'Mention Count Ranking',
  },
  {
    key: 'position',
    label: 'Avg Position',
    dataKey: 'position',
    color: 'var(--warning)',
    suffix: '',
    format: (v) => v.toFixed(1),
    deltaFormat: (c, p) => {
      const d = (p - c).toFixed(1);
      return Number(d) >= 0 ? `improved by ${d}` : `declined by ${Math.abs(Number(d)).toFixed(1)}`;
    },
    leaderboardLabel: 'Position Ranking',
  },
];
