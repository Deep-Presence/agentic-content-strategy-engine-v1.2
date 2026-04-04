'use client';

import { Card, Badge, Button } from '@/components/ui';
import {
  Mic,
  Users,
  Palette,
  RefreshCw,
  Loader2,
  ChevronRight,
  Clock,
  Building2,
  Eye,
  Swords,
  MessageSquareText,
  AlertTriangle,
  BookOpen,
} from 'lucide-react';
import type { KBDocument, VoiceGuide } from '@/types';
import type { PersonaListItemAPI, KBHealthResponseAPI } from '../_lib/types';

interface HubViewProps {
  kbDocs: KBDocument[];
  voiceGuide: VoiceGuide | null;
  personas: PersonaListItemAPI[];
  kbHealth: KBHealthResponseAPI | null;
  onNavigate: (id: string) => void;
  onRerun: () => void;
  isRerunning?: boolean;
}

const CARD_CONFIG: Record<string, { icon: React.ReactNode; color: string; bg: string }> = {
  brand_voice: { icon: <Mic size={22} strokeWidth={1.5} />, color: 'text-accent', bg: 'bg-accent-subtle' },
  audience_personas: { icon: <Users size={22} strokeWidth={1.5} />, color: 'text-info', bg: 'bg-info-subtle' },
  company_overview: { icon: <Building2 size={22} strokeWidth={1.5} />, color: 'text-success', bg: 'bg-success-subtle' },
  competitor_registry: { icon: <Swords size={22} strokeWidth={1.5} />, color: 'text-warning', bg: 'bg-warning-subtle' },
  customer_reviews: { icon: <MessageSquareText size={22} strokeWidth={1.5} />, color: 'text-info', bg: 'bg-info-subtle' },
  weakness_analysis: { icon: <AlertTriangle size={22} strokeWidth={1.5} />, color: 'text-error', bg: 'bg-error-subtle' },
  visual_brand: { icon: <Palette size={22} strokeWidth={1.5} />, color: 'text-warning', bg: 'bg-warning-subtle' },
  voice_style_guide: { icon: <BookOpen size={22} strokeWidth={1.5} />, color: 'text-accent', bg: 'bg-accent-subtle' },
  brand_perception: { icon: <Eye size={22} strokeWidth={1.5} />, color: 'text-accent', bg: 'bg-accent-subtle' },
};

interface CardItem {
  id: string;
  label: string;
  description: string;
  version?: string;
  meta?: string;
  healthStatus?: string;
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return '—';
  }
}

export function HubView({ kbDocs, voiceGuide, personas, kbHealth, onNavigate, onRerun, isRerunning }: HubViewProps) {
  // Build the flat card list from all data sources
  const cards: CardItem[] = [];

  // Brand Voice
  cards.push({
    id: 'brand_voice',
    label: 'Brand Voice',
    description: 'Voice identity, tone registers, lexicon guidelines, anti-patterns, and writing examples.',
    version: voiceGuide ? 'v1' : undefined,
    meta: voiceGuide ? '1 guide' : 'Not generated',
  });

  // Audience Personas
  cards.push({
    id: 'audience_personas',
    label: 'Audience Personas',
    description: 'Buyer personas with demographics, pain points, messaging strategy, and engagement patterns.',
    meta: `${personas.length} ${personas.length === 1 ? 'persona' : 'personas'}`,
  });

  // KB docs as individual cards
  const kbTypes: { type: string; id: string; label: string; description: string }[] = [
    { type: 'company_overview', id: 'company_overview', label: 'Company Overview', description: 'Company profile, product capabilities, target market, business model, and strategic priorities.' },
    { type: 'competitor_registry', id: 'competitor_registry', label: 'Competitor Registry', description: 'Competitive landscape analysis with feature comparisons and differentiation strategy.' },
    { type: 'customer_reviews', id: 'customer_reviews', label: 'Customer Reviews', description: 'Customer feedback analysis, NPS insights, feature requests, and success stories.' },
    { type: 'weakness_analysis', id: 'weakness_analysis', label: 'Weakness Analysis', description: 'Identified gaps in content, technical capabilities, market positioning, and documentation.' },
    { type: 'brand_perception', id: 'brand_perception', label: 'Brand Perception', description: 'Brand positioning, AI engine citations, sentiment analysis, and market perception.' },
  ];

  for (const kb of kbTypes) {
    const doc = kbDocs.find(d => d.type === kb.type);
    const docHealth = kbHealth?.doc_health?.[kb.type];
    cards.push({
      id: kb.id,
      label: kb.label,
      description: kb.description,
      version: doc?.version,
      meta: doc ? `${doc.wordCount.toLocaleString()} words` : 'Not generated',
      healthStatus: docHealth?.status,
    });
  }

  // Visual Brand Guidelines
  cards.push({
    id: 'visual_brand',
    label: 'Visual Brand Guidelines',
    description: 'Brand colors, typography, logos, and visual guidelines extracted from your website.',
    meta: 'Setup required',
  });

  // Voice Style Guide (raw markdown version)
  cards.push({
    id: 'voice_style_guide',
    label: 'Voice Style Guide',
    description: 'Full reference document with detailed writing rules, worked examples, and drift checks.',
    version: voiceGuide ? 'v1' : undefined,
    meta: voiceGuide ? 'Full document' : 'Not generated',
  });

  // Derive status from health
  const staleDocs = kbHealth?.stale_docs ?? [];
  const missingDocs = kbHealth?.missing_docs ?? [];
  const hasStale = staleDocs.length > 0;
  const hasMissing = missingDocs.length > 0;

  return (
    <div>
      {/* Page Header */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <h1 className="font-display text-[22px] font-semibold tracking-[-0.02em] text-text-primary">
            Brand Artifact
          </h1>
          <p className="text-[14px] text-text-secondary mt-1 max-w-[560px] leading-[1.5]">
            Your brand intelligence center. Knowledge base, voice guide, audience personas, and visual identity.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-[12px] text-text-tertiary mr-2">
            <Clock size={13} strokeWidth={1.5} />
            {kbHealth?.last_full_refresh
              ? `Last run: ${formatDate(kbHealth.last_full_refresh)}`
              : 'No runs yet'}
          </div>
          <Button variant="primary" onClick={onRerun} disabled={isRerunning}>
            {isRerunning ? (
              <Loader2 size={14} strokeWidth={1.5} className="mr-1.5 animate-spin" />
            ) : (
              <RefreshCw size={14} strokeWidth={1.5} className="mr-1.5" />
            )}
            {isRerunning ? 'Running...' : 'Re-run Pipeline'}
          </Button>
        </div>
      </div>

      {/* Activity bar */}
      <div className="bg-surface border border-border rounded-md px-4 py-3 mb-6 flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${hasMissing ? 'bg-error' : hasStale ? 'bg-warning' : 'bg-success'}`} />
          <span className="text-[12px] font-medium text-text-primary">
            {hasMissing ? `${missingDocs.length} missing` : hasStale ? `${staleDocs.length} stale` : 'All Fresh'}
          </span>
        </div>
        <div className="h-3 w-px bg-border" />
        <div className="flex items-center gap-4 text-[12px] text-text-secondary">
          <span>{kbDocs.length} KB docs</span>
          <span>{voiceGuide ? '1 voice guide' : 'No voice guide'}</span>
          <span>{personas.length} personas</span>
        </div>
        {kbHealth && (
          <>
            <div className="h-3 w-px bg-border" />
            <div className="flex items-center gap-1.5 text-[12px] text-text-tertiary">
              <span>Health score: <span className="font-mono font-medium text-text-primary">{Math.round(kbHealth.overall_score * 100)}%</span></span>
            </div>
          </>
        )}
        <div className="ml-auto">
          <Badge variant={hasMissing ? 'error' : hasStale ? 'warning' : 'success'}>
            {hasMissing ? 'Incomplete' : hasStale ? 'Stale docs' : 'All artifacts ready'}
          </Badge>
        </div>
      </div>

      {/* Flat Card Grid */}
      <div className="grid grid-cols-3 gap-4">
        {cards.map(card => {
          const config = CARD_CONFIG[card.id] || { icon: <BookOpen size={22} strokeWidth={1.5} />, color: 'text-text-secondary', bg: 'bg-bg' };

          return (
            <button
              key={card.id}
              onClick={() => onNavigate(card.id)}
              className="text-left group cursor-pointer"
            >
              <Card className="h-full transition-all duration-150 group-hover:border-border-strong !p-5">
                <div className="flex items-start justify-between mb-3">
                  <div className={`w-11 h-11 rounded-md ${config.bg} flex items-center justify-center`}>
                    <span className={config.color}>{config.icon}</span>
                  </div>
                  {card.healthStatus && (
                    <div className={`w-2 h-2 rounded-full mt-1 ${
                      card.healthStatus === 'fresh' ? 'bg-success' :
                      card.healthStatus === 'stale' ? 'bg-warning' :
                      card.healthStatus === 'missing' ? 'bg-error' : 'bg-text-tertiary'
                    }`} title={card.healthStatus} />
                  )}
                </div>
                <div className="flex items-center gap-2 mb-1.5">
                  <h3 className="text-[15px] font-semibold text-text-primary">{card.label}</h3>
                  <ChevronRight
                    size={14}
                    strokeWidth={1.5}
                    className="text-text-tertiary opacity-0 group-hover:opacity-100 transition-opacity ml-auto flex-shrink-0"
                  />
                </div>
                <p className="text-[13px] text-text-secondary leading-[1.6] mb-3">
                  {card.description}
                </p>
                <div className="flex items-center gap-2 pt-3 border-t border-border">
                  <span className="text-[12px] text-text-tertiary">{card.meta}</span>
                  {card.version && <Badge variant="neutral" className="ml-auto">{card.version}</Badge>}
                </div>
              </Card>
            </button>
          );
        })}
      </div>
    </div>
  );
}
