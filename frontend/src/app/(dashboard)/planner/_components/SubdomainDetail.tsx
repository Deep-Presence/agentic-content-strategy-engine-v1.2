'use client';

import { cn } from '@/lib/utils';
import { Card, Button } from '@/components/ui';
import { ArrowRight, Pencil, Move, Plus, Trash2 } from 'lucide-react';
import {
  type SubdomainNode,
  type CategoryNode,
  type Assignment,
  type ScoringEntry,
  PERSONA_MAP,
  PERSONA_IDS,
  getSourceCount,
} from './topic-data';

interface SubdomainDetailProps {
  subdomain: SubdomainNode;
  category: CategoryNode;
  onViewAssignments: () => void;
  assignments: Assignment[];
  scoring: ScoringEntry | undefined;
  companyName: string;
}

const SOURCE_KEYS = ['source_a', 'source_b', 'source_c', 'source_d'] as const;
const SOURCE_LABELS = ['A', 'B', 'C', 'D'];

function ConfidenceColor(confidence: number): string {
  if (confidence >= 0.9) return 'text-success';
  if (confidence >= 0.75) return 'text-warning';
  return 'text-error';
}

export function SubdomainDetail({ subdomain, category, onViewAssignments, assignments, scoring, companyName }: SubdomainDetailProps) {
  const sourceCount = getSourceCount(subdomain.source_provenance);
  const factors = subdomain.priority_factors;

  // Compute AEO scores
  const citationOpp = factors?.citation_opportunity ?? 0;
  const feasibility = factors?.content_authority ?? 0;
  const expectedReturn = subdomain.priority_score ?? 0;

  // Persona affinity — use inline data from taxonomy
  const personaAffinity = subdomain.persona_affinity ?? {};

  // Children (sub-children) pills
  const subChildren = subdomain.children ?? [];

  // Build "Why We Recommend" bullets from real data
  const whyBullets = buildWhyBullets(subdomain, scoring);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-[10px]">
        <span className="text-accent cursor-pointer hover:underline">{companyName}</span>
        <span className="text-text-tertiary">/</span>
        <span className="text-accent cursor-pointer hover:underline">{category.name}</span>
        <span className="text-text-tertiary">/</span>
        <span className="text-text-secondary">{subdomain.name}</span>
      </div>

      {/* Title + Description */}
      <div>
        <h2 className="text-[20px] font-semibold text-text-primary tracking-[-0.02em] leading-tight">
          {subdomain.name}
        </h2>
        <p className="text-[13px] text-text-secondary leading-relaxed mt-1.5">
          {subdomain.description}
        </p>
      </div>

      {/* Sub-children pills */}
      {subChildren.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {subChildren.map((child) => (
            <span
              key={child.id}
              className="px-2 py-[2px] text-[10px] font-medium bg-surface-raised border border-border rounded-sm text-text-secondary"
            >
              {child.name}
            </span>
          ))}
        </div>
      )}

      {/* Provenance Strip */}
      <Card hoverable={false} className="p-0">
        <div className="flex items-stretch divide-x divide-border">
          {/* Sources */}
          <div className="flex-1 px-3 py-2.5">
            <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-1">
              SOURCES
            </span>
            <div className="flex items-center gap-1.5">
              <div className="flex items-center gap-[3px]">
                {SOURCE_KEYS.map((key, i) => {
                  const has = subdomain.source_provenance[key];
                  return (
                    <span
                      key={key}
                      className={cn(
                        'w-[18px] h-[18px] flex items-center justify-center text-[9px] font-medium rounded-sm',
                        has
                          ? 'bg-accent text-text-on-accent'
                          : 'border border-border text-text-tertiary'
                      )}
                    >
                      {SOURCE_LABELS[i]}
                    </span>
                  );
                })}
              </div>
              <span className="text-[11px] text-text-secondary font-mono">{sourceCount}/4</span>
            </div>
          </div>

          {/* Confidence */}
          <div className="flex-1 px-3 py-2.5">
            <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-1">
              CONFIDENCE
            </span>
            <span className={cn('text-[18px] font-semibold font-mono', ConfidenceColor(subdomain.confidence))}>
              {(subdomain.confidence * 100).toFixed(0)}%
            </span>
          </div>

          {/* Assignments */}
          <div className="flex-1 px-3 py-2.5">
            <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-1">
              ASSIGNMENTS
            </span>
            <span className="text-[18px] font-semibold font-mono text-accent">
              {assignments.length}
            </span>
          </div>
        </div>
      </Card>

      {/* AEO Scoring */}
      <Card hoverable={false}>
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-2">
          AEO SCORING
        </span>
        <p className="text-[11px] font-mono text-text-tertiary mb-3">
          Expected Return = P(cited) x Value(citation) x Feasibility
        </p>

        <div className="space-y-3">
          <ScoreBar
            label="Expected Return"
            description="Combined probability x impact x feasibility"
            score={expectedReturn}
          />
          <ScoreBar
            label="Citation Opportunity"
            description="Supply-gap whitespace — niche BOFU scores highest"
            score={citationOpp}
          />
          <ScoreBar
            label="Feasibility"
            description="Ability to produce authoritative content"
            score={feasibility}
          />
        </div>
      </Card>

      {/* Persona Affinity */}
      <Card hoverable={false}>
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-2">
          PERSONA AFFINITY
        </span>
        <div className="flex items-start gap-3">
          {PERSONA_IDS.map((pid) => {
            const score = personaAffinity[pid] ?? 0;
            const persona = PERSONA_MAP[pid];
            const opacity = Math.max(0.05, Math.min(0.45, score * 0.5));
            return (
              <div key={pid} className="flex flex-col items-center gap-1">
                <span className="text-[9px] font-semibold text-text-tertiary uppercase">
                  {persona.short}
                </span>
                <div
                  className="w-[36px] h-[26px] rounded-sm flex items-center justify-center text-[10px] font-mono font-medium"
                  style={{
                    backgroundColor: `var(--accent)`,
                    opacity: opacity + 0.3,
                    color: opacity > 0.25 ? 'var(--text-on-accent)' : 'var(--accent)',
                  }}
                >
                  {score.toFixed(2)}
                </div>
                <span className="text-[9px] text-text-tertiary text-center max-w-[60px] leading-tight">
                  {persona.full}
                </span>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Why We Recommend This */}
      <Card hoverable={false}>
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-accent block mb-2">
          WHY WE RECOMMEND THIS
        </span>
        <div className="space-y-2">
          {whyBullets.map((bullet, i) => (
            <div key={i} className="flex items-start gap-2">
              <div className="w-[5px] h-[5px] rounded-full bg-accent shrink-0 mt-[6px]" />
              <p className="text-[12px] text-text-secondary leading-[1.5]">{bullet}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Node Actions */}
      <Card hoverable={false}>
        <div className="flex flex-wrap items-center gap-2">
          {assignments.length > 0 ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={onViewAssignments}
              className="bg-accent-subtle text-accent hover:bg-accent/10"
            >
              View Assignments
              <ArrowRight size={11} strokeWidth={1.5} className="ml-1" />
            </Button>
          ) : (
            <Button variant="ghost" size="sm" disabled>
              No Assignments Yet
            </Button>
          )}
          <Button variant="secondary" size="sm">
            <Pencil size={10} strokeWidth={1.5} className="mr-1" />
            Edit
          </Button>
          <Button variant="secondary" size="sm">
            <Move size={10} strokeWidth={1.5} className="mr-1" />
            Move
          </Button>
          <Button variant="secondary" size="sm">
            <Plus size={10} strokeWidth={1.5} className="mr-1" />
            Add Child
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="bg-error-subtle text-error hover:bg-error/10"
          >
            <Trash2 size={10} strokeWidth={1.5} className="mr-1" />
            Delete
          </Button>
        </div>
      </Card>
    </div>
  );
}

// ─── Score Bar Component ─────────────────────────────────

function ScoreBar({
  label,
  description,
  score,
}: {
  label: string;
  description: string;
  score: number;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-0.5">
        <div>
          <span className="text-[12px] font-semibold text-text-primary">{label}</span>
          <span className="text-[10px] text-text-tertiary ml-2">{description}</span>
        </div>
        <span className="text-[14px] font-semibold text-accent font-mono">
          {score.toFixed(2)}
        </span>
      </div>
      <div className="w-full h-[4px] bg-border rounded-full overflow-hidden">
        <div
          className="h-full bg-accent rounded-full transition-[width] duration-300"
          style={{ width: `${score * 100}%` }}
        />
      </div>
    </div>
  );
}

// ─── Why Bullets Builder ─────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function buildWhyBullets(sub: SubdomainNode, _scoring: ScoringEntry | undefined): string[] {
  const bullets: string[] = [];
  const factors = sub.priority_factors;

  // Point 1: Citation gap analysis
  const citationOpp = factors?.citation_opportunity ?? 0;
  if (citationOpp > 0.7) {
    bullets.push(
      `High citation whitespace detected — citation opportunity score of ${citationOpp.toFixed(2)} indicates significant gaps in current AI engine coverage for this topic. Content targeting this subdomain has strong potential to capture unclaimed citations.`
    );
  } else if (citationOpp > 0.5) {
    bullets.push(
      `Moderate citation opportunity at ${citationOpp.toFixed(2)} — some competitor coverage exists but there are exploitable gaps, especially in emerging subtopics and long-tail queries.`
    );
  } else {
    bullets.push(
      `Competitive landscape is dense with citation opportunity at ${citationOpp.toFixed(2)} — recommend differentiated angle focusing on proprietary data or unique methodology.`
    );
  }

  // Point 2: Strategic centrality + authority
  const centrality = factors?.strategic_centrality ?? 0;
  const authority = factors?.content_authority ?? 0;
  bullets.push(
    `Strategic centrality score of ${centrality.toFixed(2)} with content authority at ${authority.toFixed(2)} — ${
      centrality > 0.85
        ? 'this topic is core to brand positioning and product narrative'
        : 'this topic supports adjacent brand authority'
    }. ${sub.metadata?.scoring_rationale?.split('.')[0] ?? 'Strong alignment with content strategy'}.`
  );

  // Point 3: Conversion potential + persona alignment
  const conversion = factors?.conversion_potential ?? 0;
  const topPersona = Object.entries(sub.persona_affinity ?? {}).sort(
    (a, b) => b[1] - a[1]
  )[0];
  const personaName = topPersona ? PERSONA_MAP[topPersona[0]]?.full ?? topPersona[0] : 'target audience';
  const personaScore = topPersona ? topPersona[1] : 0;
  bullets.push(
    `Conversion potential of ${conversion.toFixed(2)} with highest persona affinity for ${personaName} (${personaScore.toFixed(2)}) — ${
      conversion > 0.7
        ? 'content in this subdomain directly supports purchase decision-making'
        : 'drives awareness and consideration-stage engagement'
    }.`
  );

  return bullets;
}
