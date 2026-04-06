'use client';

import type { ContentCard } from './types';
import { getColumn, getDisplay, getWorkerStepIndex } from '../_lib/status-adapter';

const OVERLINE: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  color: 'var(--text-tertiary)',
  marginBottom: 8,
};

function QueueSidebar({ card }: { card: ContentCard }) {
  return (
    <div className="p-4 space-y-4">
      <div style={OVERLINE}>Opportunity Summary</div>

      <div className="space-y-3">
        {[
          { label: 'Gap score', value: `~${Math.round(card.gap * 100)}`, color: 'var(--error)', mono: true },
          { label: 'Priority', value: card.priority, color: 'var(--warning)', mono: false },
          { label: 'Read time', value: `${card.readTime} min`, color: 'var(--text-primary)', mono: true },
        ].map((item) => (
          <div key={item.label} className="flex items-center justify-between">
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{item.label}</span>
            <span style={{ fontSize: 12, fontFamily: item.mono ? 'var(--font-mono)' : undefined, fontWeight: 600, color: item.color }}>
              {item.value}
            </span>
          </div>
        ))}
        <div className="flex items-center justify-between">
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Competitor</span>
          <div className="flex items-center gap-1">
            <img
              src={`https://www.google.com/s2/favicons?domain=${card.competitor}&sz=32`}
              alt={card.competitor}
              width={12}
              height={12}
              style={{ borderRadius: 2 }}
            />
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{card.competitor}</span>
          </div>
        </div>
      </div>

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
        <div style={OVERLINE}>Why this topic</div>
        <ul className="space-y-2">
          {(card.briefContent?.reasons && card.briefContent.reasons.length > 0)
            ? card.briefContent.reasons.map((reason, i) => (
                <li key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{reason}</li>
              ))
            : (
              <>
                <li style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  Gap score indicates content opportunity
                </li>
                <li style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  High citation correlation for {card.type.replace('_', ' ').toLowerCase()} format
                </li>
              </>
            )
          }
        </ul>
      </div>
    </div>
  );
}

function BriefSidebar({ card }: { card: ContentCard }) {
  const brief = card.briefContent;
  if (!brief) return null;

  return (
    <div className="p-4 space-y-4">
      <div>
        <div style={OVERLINE}>Brief Outline</div>
        <ol className="space-y-1" style={{ paddingLeft: 16 }}>
          {brief.sections.map((section, i) => (
            <li key={i} style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.6, cursor: 'pointer' }}>
              {section}
            </li>
          ))}
        </ol>
      </div>

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
        <div style={OVERLINE}>Sources Across AI Engines</div>
        <div className="space-y-2">
          {brief.sources.map((source) => (
            <div
              key={source.domain}
              className="flex items-center gap-2 p-2"
              style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--bg)' }}
            >
              <img
                src={`https://www.google.com/s2/favicons?domain=${source.domain}&sz=32`}
                alt={source.domain}
                width={14}
                height={14}
                style={{ borderRadius: 2 }}
              />
              <div className="flex-1 min-w-0">
                <div className="truncate" style={{ fontSize: 11, color: 'var(--text-primary)' }}>{source.name}</div>
                <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{source.domain}</div>
              </div>
              <span style={{
                fontSize: 9, fontWeight: 600, fontFamily: 'var(--font-mono)',
                padding: '1px 5px', borderRadius: 'var(--radius-full)',
                background: 'var(--accent-subtle)', color: 'var(--accent)',
              }}>
                {source.engines} engines
              </span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
        <div style={OVERLINE}>Why We Picked This</div>
        <ul className="space-y-2">
          {brief.reasons.map((reason, i) => (
            <li key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{reason}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ArticleSidebar({ card, activeSection, onSectionClick }: {
  card: ContentCard;
  activeSection: number;
  onSectionClick: (index: number) => void;
}) {
  const sections = card.articleContent?.sections || [];
  const totalWords = sections.reduce((sum, s) => sum + s.words, 0);

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-2">
        <div style={OVERLINE}>Sections</div>
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>
          {totalWords.toLocaleString()}w total
        </span>
      </div>
      <div className="space-y-0.5">
        {sections.map((section, i) => {
          const isActive = activeSection === i;
          return (
            <button
              key={i}
              onClick={() => onSectionClick(i)}
              className="w-full text-left flex items-center justify-between"
              style={{
                padding: '7px 10px',
                fontSize: 12,
                color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                fontWeight: isActive ? 500 : 400,
                background: isActive ? 'var(--accent-subtle)' : 'transparent',
                borderLeft: isActive ? '2px solid var(--accent)' : '2px solid transparent',
                borderTop: 'none',
                borderRight: 'none',
                borderBottom: 'none',
                borderRadius: '0 var(--radius-sm) var(--radius-sm) 0',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              <span className="truncate" style={{ marginRight: 8 }}>{section.heading}</span>
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)', flexShrink: 0 }}>
                {section.words}w
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// Pipeline steps aligned with backend worker chain
const SIDEBAR_STEPS = [
  { key: 'briefing', label: 'Brief', desc: 'Building brief' },
  { key: 'outlining', label: 'Outline', desc: 'Section structure' },
  { key: 'drafting', label: 'Draft', desc: 'Content creation' },
  { key: 'linking', label: 'Link', desc: 'Internal links' },
  { key: 'enriching', label: 'Enrich', desc: 'Fact checking' },
  { key: 'evaluating', label: 'Evaluate', desc: 'Quality scoring' },
];

function AgentSidebar({ card }: { card: ContentCard }) {
  const progress = card.agentProgress;
  const display = getDisplay(card.status);
  const stepIndex = getWorkerStepIndex(card.status);

  return (
    <div className="p-4 space-y-4">
      {/* Progress summary */}
      <div>
        <div style={OVERLINE}>Current Stage</div>
        <div className="flex items-center gap-2 mb-2">
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: display.isAgentActive ? 'var(--warning)' : 'var(--border)',
              animation: display.isAgentActive ? 'pulse 1.5s ease-in-out infinite' : undefined,
            }}
          />
          <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
            {display.label}
          </span>
        </div>
        {progress && (
          <>
            <div className="flex items-center gap-2">
              <div className="flex-1" style={{ height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{
                  width: `${progress.pct}%`,
                  height: '100%',
                  borderRadius: 2,
                  background: progress.pct > 80 ? 'var(--success)' : progress.pct >= 50 ? 'var(--accent)' : 'var(--warning)',
                  animation: 'progressPulse 2.5s ease-in-out infinite',
                  transition: 'width 0.6s ease',
                }} />
              </div>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>
                {progress.pct}%
              </span>
            </div>
            {progress.wordsCurrent !== undefined && (
              <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)', marginTop: 4 }}>
                {progress.wordsCurrent.toLocaleString()} / {progress.wordsTarget?.toLocaleString()} words
              </div>
            )}
          </>
        )}
      </div>

      {/* Pipeline stages */}
      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
        <div style={OVERLINE}>Pipeline</div>
        <div className="space-y-1">
          {SIDEBAR_STEPS.map((stage, i) => {
            const done = stepIndex > i;
            const active = stage.key === card.status;

            return (
              <div key={stage.key} className="flex items-center gap-2 py-1.5">
                <span style={{
                  width: 18,
                  height: 18,
                  borderRadius: '50%',
                  background: done ? 'var(--success)' : active ? 'var(--warning)' : 'var(--border)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 9,
                  fontWeight: 600,
                  color: done || active ? '#fff' : 'var(--text-tertiary)',
                  flexShrink: 0,
                  animation: active ? 'pulse 2s ease-in-out infinite' : undefined,
                }}>
                  {done ? '\u2713' : i + 1}
                </span>
                <div>
                  <div style={{ fontSize: 11, fontWeight: active ? 500 : 400, color: done || active ? 'var(--text-primary)' : 'var(--text-tertiary)' }}>
                    {stage.label}
                  </div>
                  <div style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>{stage.desc}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Current task */}
      {progress && (
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <div style={OVERLINE}>Current Task</div>
          <div className="flex items-start gap-2">
            <span style={{
              width: 4, height: 4, borderRadius: '50%', background: 'var(--warning)',
              marginTop: 5, flexShrink: 0,
              animation: 'pulse 1.5s ease-in-out infinite',
            }} />
            <div style={{ fontSize: 11, color: 'var(--text-primary)', animation: 'typing 1.8s ease-in-out infinite', lineHeight: 1.5 }}>
              {progress.currentTask}
            </div>
          </div>
        </div>
      )}

      {/* Stats */}
      {progress?.sectionsComplete !== undefined && (
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <div style={OVERLINE}>Stats</div>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--bg)' }}>
              <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 2 }}>Sections</div>
              <div style={{ fontSize: 14, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
                {progress.sectionsComplete}/{progress.sectionsTotal}
              </div>
            </div>
            <div className="p-2" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--bg)' }}>
              <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 2 }}>Words</div>
              <div style={{ fontSize: 14, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
                {(progress.wordsCurrent || 0).toLocaleString()}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Brief content (shown during production stages when brief is available) */}
      {card.briefContent && (
        <>
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
            <div style={OVERLINE}>Brief Outline</div>
            <div className="space-y-1">
              {card.briefContent.sections.map((section, i) => (
                <div key={i} className="flex items-start gap-2" style={{ fontSize: 11, color: 'var(--text-primary)', lineHeight: 1.5 }}>
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)', width: 16, flexShrink: 0 }}>{i + 1}.</span>
                  {section}
                </div>
              ))}
            </div>
          </div>

          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
            <div style={OVERLINE}>Brief Targets</div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Target words</span>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>
                  {card.briefContent.targetWords.toLocaleString()}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Exemplars</span>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>
                  {card.briefContent.exemplarCount}
                </span>
              </div>
            </div>
          </div>

          {card.briefContent.reasons.length > 0 && (
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
              <div style={OVERLINE}>Key Angles</div>
              <div className="space-y-1.5">
                {card.briefContent.reasons.map((reason, i) => (
                  <div key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    {reason}
                  </div>
                ))}
              </div>
            </div>
          )}

          {card.briefContent.sources.length > 0 && (
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
              <div style={OVERLINE}>Sources</div>
              <div className="space-y-1.5">
                {card.briefContent.sources.slice(0, 5).map((src, i) => (
                  <div key={i} className="flex items-center gap-2">
                    {src.domain && (
                      <img
                        src={`https://www.google.com/s2/favicons?domain=${src.domain}&sz=32`}
                        alt={src.domain}
                        width={12}
                        height={12}
                        style={{ borderRadius: 2, flexShrink: 0 }}
                      />
                    )}
                    <span className="truncate" style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                      {src.domain || src.name}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// GA total steps (used for progress fraction only — labels not exposed)
const GA_TOTAL_STEPS = 8;

const BUYER_STAGE_COLORS: Record<string, { bg: string; color: string }> = {
  tofu: { bg: 'var(--accent-subtle)', color: 'var(--accent)' },
  mofu: { bg: 'var(--warning-subtle)', color: 'var(--warning)' },
  bofu: { bg: 'var(--success-subtle)', color: 'var(--success)' },
};

const INTENT_COLORS: Record<string, { bg: string; color: string }> = {
  informational: { bg: 'var(--accent-subtle)', color: 'var(--accent)' },
  commercial: { bg: 'var(--warning-subtle)', color: 'var(--warning)' },
  navigational: { bg: 'var(--surface)', color: 'var(--text-secondary)' },
  transactional: { bg: 'var(--success-subtle)', color: 'var(--success)' },
};

const FORMAT_LABELS: Record<string, string> = {
  comprehensive_guide: 'Comprehensive Guide',
  long_form_article: 'Long-form Article',
  comparison_guide: 'Comparison Guide',
  how_to_guide: 'How-to Guide',
  explainer: 'Explainer',
  listicle: 'Listicle',
  case_study: 'Case Study',
  tutorial: 'Tutorial',
};

const FACTOR_LABELS: Record<string, string> = {
  citation_opportunity: 'Citation Opp.',
  conversion_potential: 'Conversion',
  strategic_centrality: 'Centrality',
  content_authority: 'Authority',
};

function formatPersonaName(raw: string): string {
  if (!raw) return '';
  return raw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function GapAnalysisSidebar({ card }: { card: ContentCard }) {
  const progress = card.agentProgress;
  const display = getDisplay(card.status);
  const currentStepNum = progress?.gaStepNum ?? 0;

  return (
    <div className="p-4 space-y-4">
      {/* Topic info */}
      <div>
        <div style={OVERLINE}>Topic</div>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', lineHeight: 1.4, marginBottom: 4 }}>
          {card.title}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
          {card.cluster}
        </div>
        {card.description && (
          <p style={{ fontSize: 11, color: 'var(--text-tertiary)', lineHeight: 1.5, marginTop: 6 }}>
            {card.description}
          </p>
        )}
      </div>

      {/* Buyer stage + Intent type badges */}
      {(card.buyerStage || card.intentType) && (
        <div className="flex items-center gap-1.5 flex-wrap">
          {card.buyerStage && (() => {
            const style = BUYER_STAGE_COLORS[card.buyerStage.toLowerCase()];
            return (
              <span style={{
                fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
                padding: '2px 8px', borderRadius: 'var(--radius-full)',
                background: style?.bg ?? 'var(--border)', color: style?.color ?? 'var(--text-secondary)',
              }}>
                {card.buyerStage.toUpperCase()}
              </span>
            );
          })()}
          {card.intentType && (() => {
            const style = INTENT_COLORS[card.intentType.toLowerCase()];
            return (
              <span style={{
                fontSize: 10, fontWeight: 600, textTransform: 'capitalize',
                padding: '2px 8px', borderRadius: 'var(--radius-full)',
                border: '1px solid var(--border)',
                background: style?.bg ?? 'var(--border)', color: style?.color ?? 'var(--text-secondary)',
              }}>
                {card.intentType}
              </span>
            );
          })()}
        </div>
      )}

      {/* Content Specification */}
      {(card.contentFormat || card.estimatedWordCount || card.citationOpp != null) && (
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <div style={OVERLINE}>Content Spec</div>
          <div className="space-y-2">
            {card.contentFormat && (
              <div className="flex items-center justify-between">
                <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Format</span>
                <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-primary)' }}>
                  {FORMAT_LABELS[card.contentFormat] ?? card.contentFormat.replace(/_/g, ' ')}
                </span>
              </div>
            )}
            {card.estimatedWordCount != null && card.estimatedWordCount > 0 && (
              <div className="flex items-center justify-between">
                <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Word count</span>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>
                  ~{card.estimatedWordCount.toLocaleString()}
                </span>
              </div>
            )}
            {card.citationOpp != null && (
              <div className="flex items-center justify-between">
                <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Citation opp.</span>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--accent)' }}>
                  {Math.round(card.citationOpp * 100)}%
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Target Keywords */}
      {card.targetKeywords && (card.targetKeywords.primary || (card.targetKeywords.secondary && card.targetKeywords.secondary.length > 0)) && (
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <div style={OVERLINE}>Target Keywords</div>
          {card.targetKeywords.primary && (
            <div
              className="p-2 rounded-md mb-2"
              style={{ border: '1px solid var(--accent)', background: 'var(--accent-subtle)' }}
            >
              <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-primary)' }}>
                {card.targetKeywords.primary}
              </div>
              <span style={{ fontSize: 9, fontWeight: 600, color: 'var(--accent)', textTransform: 'uppercase' }}>
                Primary keyword
              </span>
            </div>
          )}
          {card.targetKeywords.secondary && card.targetKeywords.secondary.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {card.targetKeywords.secondary.map((kw, i) => (
                <span
                  key={i}
                  style={{
                    fontSize: 10, padding: '2px 6px', borderRadius: 'var(--radius-full)',
                    border: '1px solid var(--border)', color: 'var(--text-secondary)',
                  }}
                >
                  {kw}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Why We Recommend (content angle + top priority factor) */}
      {(card.contentAngle || (card.priorityFactors && Object.keys(card.priorityFactors).length > 0)) && (
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <div style={OVERLINE}>Why This Topic</div>
          <div className="space-y-2">
            {card.contentAngle && (
              <div className="p-2 rounded-md" style={{ border: '1px solid var(--border)', borderLeft: '2px solid var(--warning)' }}>
                <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 2 }}>Content Angle</div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{card.contentAngle}</div>
              </div>
            )}
            {card.priorityFactors && Object.entries(card.priorityFactors).length > 0 && (
              <div className="space-y-1.5">
                {Object.entries(card.priorityFactors)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 3)
                  .map(([key, val]) => (
                    <div key={key} className="flex items-center justify-between">
                      <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                        {FACTOR_LABELS[key] ?? key.replace(/_/g, ' ')}
                      </span>
                      <div className="flex items-center gap-1.5">
                        <div style={{ width: 40, height: 3, borderRadius: 2, background: 'var(--border)', overflow: 'hidden' }}>
                          <div style={{ width: `${Math.round(val * 100)}%`, height: '100%', borderRadius: 2, background: 'var(--accent)' }} />
                        </div>
                        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)', width: 28, textAlign: 'right' }}>
                          {Math.round(val * 100)}%
                        </span>
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Persona Affinity */}
      {card.personaName && (
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <div style={OVERLINE}>Target Persona</div>
          <div className="flex items-center gap-2 mb-2">
            <div
              className="flex items-center justify-center rounded-full text-white shrink-0"
              style={{ width: 22, height: 22, fontSize: 9, fontWeight: 600, background: 'var(--accent)' }}
            >
              {formatPersonaName(card.personaName).split(' ').map(w => w[0]).join('').slice(0, 2)}
            </div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>
                {formatPersonaName(card.personaName)}
              </div>
              <div style={{ fontSize: 9, fontWeight: 600, color: 'var(--accent)', textTransform: 'uppercase' }}>
                Primary target
              </div>
            </div>
          </div>
          {card.personaAffinity && Object.keys(card.personaAffinity).length > 0 && (
            <div className="space-y-1">
              {Object.entries(card.personaAffinity)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 4)
                .map(([pid, score]) => (
                  <div key={pid} className="flex items-center justify-between">
                    <span style={{ fontSize: 11, color: pid === card.personaId ? 'var(--text-primary)' : 'var(--text-secondary)', fontWeight: pid === card.personaId ? 500 : 400 }}>
                      {formatPersonaName(pid)}
                    </span>
                    <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>
                      {Math.round(score * 100)}%
                    </span>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}

      {/* Current GA progress */}
      {card.status === 'gap_analysis' && progress && (
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <div style={OVERLINE}>Analysis Progress</div>
          <div className="flex items-center gap-2 mb-2">
            <span
              style={{
                width: 6, height: 6, borderRadius: '50%',
                background: display.isAgentActive ? 'var(--warning)' : 'var(--border)',
                animation: display.isAgentActive ? 'pulse 1.5s ease-in-out infinite' : undefined,
              }}
            />
            <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>
              {progress.currentTask || display.label}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1" style={{ height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{
                width: `${progress.pct}%`, height: '100%', borderRadius: 2,
                background: progress.pct > 80 ? 'var(--success)' : progress.pct >= 50 ? 'var(--accent)' : 'var(--warning)',
                animation: 'progressPulse 2.5s ease-in-out infinite',
                transition: 'width 0.6s ease',
              }} />
            </div>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>
              {progress.pct}%
            </span>
          </div>
        </div>
      )}

      {/* GA pipeline progress (abstract — no step names) */}
      {card.status === 'gap_analysis' && (
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <div style={OVERLINE}>Pipeline</div>
          {/* Step dots — filled/empty, no labels */}
          <div className="flex items-center gap-1.5 mb-3">
            {Array.from({ length: GA_TOTAL_STEPS }, (_, i) => {
              const stepNum = i + 1;
              const done = stepNum < currentStepNum;
              const active = stepNum === currentStepNum;
              return (
                <div
                  key={i}
                  style={{
                    width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                    background: done ? 'var(--success)' : active ? 'var(--warning)' : 'var(--border)',
                    animation: active ? 'pulse 2s ease-in-out infinite' : undefined,
                  }}
                />
              );
            })}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
            Step {currentStepNum} of {GA_TOTAL_STEPS}
          </div>
        </div>
      )}

      {/* About / status message */}
      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
        <div style={OVERLINE}>About</div>
        {card.status === 'gap_analysis_complete' ? (
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Gap analysis complete. Click &ldquo;Start Production&rdquo; to begin content creation.
          </p>
        ) : card.status === 'gap_analysis' ? (
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Analyzing content gaps across AI search platforms for this topic.
          </p>
        ) : (
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Queued for gap analysis. Will identify content opportunities across AI platforms.
          </p>
        )}
      </div>
    </div>
  );
}

interface LeftSidebarProps {
  card: ContentCard;
  activeSection: number;
  onSectionClick: (index: number) => void;
}

export function LeftSidebar({ card, activeSection, onSectionClick }: LeftSidebarProps) {
  const column = getColumn(card.status);
  const isGAPhase = card.status === 'gap_analysis_pending' || card.status === 'gap_analysis' || card.status === 'gap_analysis_complete';
  const showBrief = card.status === 'brief_review' || card.status === 'pending_brief_approval';
  const showArticle = card.status === 'review' || card.status === 'pending_content_approval';

  return (
    <div
      className="overflow-y-auto h-full"
      style={{
        width: 260,
        borderRight: '1px solid var(--border)',
        background: 'var(--surface)',
        flexShrink: 0,
      }}
    >
      {isGAPhase && <GapAnalysisSidebar card={card} />}
      {!isGAPhase && card.status === 'suggested' && <QueueSidebar card={card} />}
      {showBrief && <BriefSidebar card={card} />}
      {showArticle && <ArticleSidebar card={card} activeSection={activeSection} onSectionClick={onSectionClick} />}
      {!isGAPhase && column === 'agent' && <AgentSidebar card={card} />}
    </div>
  );
}
