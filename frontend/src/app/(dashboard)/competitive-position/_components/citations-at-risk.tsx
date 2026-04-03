'use client';

import { useState } from 'react';
import { AlertTriangle, Check, Shield, FileQuestion, ArrowRight, Plus, X } from 'lucide-react';
import { CITATIONS_AT_RISK, ENGINE_DOMAINS, type CitationAtRisk } from './data';
import { BrandLogo } from './brand-logo';
import { SlideDrawer } from './slide-drawer';

function StatusGroup({
  label,
  icon: Icon,
  iconColor,
  bgColor,
  items,
  onRecapture,
  startDelay,
}: {
  label: string;
  icon: typeof AlertTriangle;
  iconColor: string;
  bgColor: string;
  items: CitationAtRisk[];
  onRecapture?: (item: CitationAtRisk) => void;
  startDelay: number;
}) {
  if (items.length === 0) return null;

  return (
    <div>
      <div
        style={{
          padding: '6px 14px',
          background: bgColor,
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
        }}
      >
        <Icon size={12} strokeWidth={2} style={{ color: iconColor }} />
        <span style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: iconColor }}>
          {label} ({items.length})
        </span>
      </div>
      {items.map((item, i) => (
        <CitationRow key={item.query} item={item} onRecapture={onRecapture} delay={startDelay + i * 40} />
      ))}
    </div>
  );
}

function CitationRow({
  item,
  onRecapture,
  delay,
}: {
  item: CitationAtRisk;
  onRecapture?: (item: CitationAtRisk) => void;
  delay: number;
}) {
  const isLost = item.status === 'lost';
  const isAtRisk = item.status === 'at_risk';
  const isStable = item.status === 'stable';
  const isNeverHad = item.status === 'never_had';

  return (
    <div
      style={{
        padding: '10px 14px',
        borderBottom: '1px solid var(--border-subtle)',
        animation: `fadeUp 300ms ease ${delay}ms both`,
      }}
    >
      {/* Query */}
      <p style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
        &ldquo;{item.query}&rdquo;
      </p>

      {/* Detail line */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px', flexWrap: 'wrap' }}>
        {isLost && item.competitor && item.engine && (
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
            Lost to <BrandLogo domain={item.competitor} size={12} /> {item.competitor} on{' '}
            <BrandLogo domain={ENGINE_DOMAINS[item.engine] || ''} size={12} /> {item.engine}
            {item.daysAgo && <span style={{ color: 'var(--text-tertiary)' }}> · {item.daysAgo} days ago</span>}
          </span>
        )}

        {isAtRisk && (
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
            {item.detail}
            {item.engine && (
              <>
                {' '}on <BrandLogo domain={ENGINE_DOMAINS[item.engine] || ''} size={12} /> {item.engine}
              </>
            )}
          </span>
        )}

        {isStable && (
          <span style={{ fontSize: '12px', color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Check size={12} strokeWidth={2} /> {item.detail}
          </span>
        )}

        {isNeverHad && item.competitor && (
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <BrandLogo domain={item.competitor} size={12} /> {item.competitor} cited on {item.engines} platforms
          </span>
        )}
      </div>

      {/* Reason */}
      {item.reason && !isStable && (
        <p style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '3px' }}>
          {item.reason}
        </p>
      )}

      {/* Action buttons */}
      {(isLost || isAtRisk || isNeverHad) && (
        <div style={{ marginTop: '6px' }}>
          {isLost && (
            <button
              onClick={() => onRecapture?.(item)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                height: '26px',
                padding: '0 8px',
                borderRadius: '4px',
                border: '1px solid var(--error)',
                background: 'transparent',
                color: 'var(--error)',
                fontSize: '11px',
                fontWeight: 500,
                cursor: 'pointer',
                fontFamily: 'var(--font-display)',
              }}
            >
              <ArrowRight size={12} strokeWidth={1.5} />
              Recapture
            </button>
          )}
          {isAtRisk && (
            <button
              onClick={() => onRecapture?.(item)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                height: '26px',
                padding: '0 8px',
                borderRadius: '4px',
                border: '1px solid var(--warning)',
                background: 'transparent',
                color: 'var(--warning)',
                fontSize: '11px',
                fontWeight: 500,
                cursor: 'pointer',
                fontFamily: 'var(--font-display)',
              }}
            >
              <Shield size={12} strokeWidth={1.5} />
              Defend
            </button>
          )}
          {isNeverHad && (
            <button
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                height: '26px',
                padding: '0 8px',
                borderRadius: '4px',
                border: '1px solid var(--border)',
                background: 'transparent',
                color: 'var(--text-secondary)',
                fontSize: '11px',
                fontWeight: 500,
                cursor: 'pointer',
                fontFamily: 'var(--font-display)',
              }}
            >
              <Plus size={12} strokeWidth={1.5} />
              {item.reason?.includes('no competing') ? 'Create' : 'Improve content'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function CitationsAtRisk() {
  const [recaptureItem, setRecaptureItem] = useState<CitationAtRisk | null>(null);

  const lost = CITATIONS_AT_RISK.filter((c) => c.status === 'lost');
  const atRisk = CITATIONS_AT_RISK.filter((c) => c.status === 'at_risk');
  const stable = CITATIONS_AT_RISK.filter((c) => c.status === 'stable');
  const neverHad = CITATIONS_AT_RISK.filter((c) => c.status === 'never_had');

  return (
    <>
      <div style={{ border: '1px solid var(--border)', borderRadius: '6px', overflow: 'hidden' }}>
        {/* Header */}
        <div style={{ padding: '14px', borderBottom: '1px solid var(--border)' }}>
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
            Citations at Risk
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Early warning system — citations you hold, are losing, or never had
          </p>
        </div>

        <StatusGroup label="Lost" icon={X} iconColor="var(--error)" bgColor="var(--error-subtle)" items={lost} onRecapture={setRecaptureItem} startDelay={0} />
        <StatusGroup label="At Risk" icon={AlertTriangle} iconColor="var(--warning)" bgColor="var(--warning-subtle)" items={atRisk} onRecapture={setRecaptureItem} startDelay={lost.length * 40} />
        <StatusGroup label="Stable" icon={Shield} iconColor="var(--success)" bgColor="var(--success-subtle)" items={stable} startDelay={(lost.length + atRisk.length) * 40} />
        <StatusGroup label="Never Had" icon={FileQuestion} iconColor="var(--text-tertiary)" bgColor="var(--surface)" items={neverHad} startDelay={(lost.length + atRisk.length + stable.length) * 40} />
      </div>

      {/* Recapture Action Panel */}
      <SlideDrawer
        isOpen={!!recaptureItem}
        onClose={() => setRecaptureItem(null)}
        title={recaptureItem ? `${recaptureItem.status === 'lost' ? 'Recapture' : 'Defend'}: "${recaptureItem.query}"` : ''}
        width="400px"
      >
        {recaptureItem && (
          <div style={{ paddingTop: '16px' }}>
            {/* What Happened */}
            <div style={{ marginBottom: '20px' }}>
              <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                What Happened
              </p>
              <p style={{ fontSize: '12px', color: 'var(--text-primary)', lineHeight: 1.6 }}>
                {recaptureItem.status === 'lost' && recaptureItem.competitor
                  ? `${recaptureItem.competitor} published new content that AI engines now prefer. ${recaptureItem.reason || ''}`
                  : recaptureItem.reason || recaptureItem.detail || 'Position weakening due to increased competition.'}
              </p>
            </div>

            {/* Your Current Content */}
            {recaptureItem.yourContent && (
              <div style={{ marginBottom: '20px' }}>
                <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Your Current Content
                </p>
                <p style={{ fontSize: '12px', color: 'var(--text-primary)' }}>
                  &ldquo;{recaptureItem.yourContent.title}&rdquo;
                </p>
                <div style={{ display: 'flex', gap: '12px', marginTop: '4px', fontSize: '11px', color: 'var(--text-tertiary)' }}>
                  <span><span style={{ fontFamily: 'var(--font-mono)' }}>{recaptureItem.yourContent.words.toLocaleString()}</span> words</span>
                  <span><span style={{ fontFamily: 'var(--font-mono)' }}>{recaptureItem.yourContent.age}</span> days old</span>
                </div>
              </div>
            )}

            {/* Structural Checklist */}
            <div style={{ marginBottom: '20px' }}>
              <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                To {recaptureItem.status === 'lost' ? 'Recapture' : 'Defend'} This Citation
              </p>
              {[
                { done: false, text: 'Add FAQ section (top-cited content has this 72% of the time)' },
                { done: false, text: 'Add comparison table (competing content has one)' },
                { done: false, text: 'Expand to 2,500+ words (you\'re at ~2,000)' },
                { done: false, text: 'Update with March 2026 data (yours references older data)' },
                { done: true, text: 'Your header structure is good (16 headers)' },
                { done: true, text: 'Your reading level is appropriate (grade 10.2)' },
              ].map((item, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', padding: '4px 0' }}>
                  {item.done ? (
                    <Check size={13} strokeWidth={2} style={{ color: 'var(--success)', flexShrink: 0, marginTop: '1px' }} />
                  ) : (
                    <X size={13} strokeWidth={2} style={{ color: 'var(--error)', flexShrink: 0, marginTop: '1px' }} />
                  )}
                  <span style={{ fontSize: '12px', color: item.done ? 'var(--text-tertiary)' : 'var(--text-primary)', lineHeight: 1.5 }}>
                    {item.text}
                  </span>
                </div>
              ))}
            </div>

            {/* Estimated Impact */}
            <div
              style={{
                padding: '10px 12px',
                background: 'var(--accent-subtle)',
                border: '1px solid rgba(91,164,196,0.2)',
                borderRadius: '6px',
                marginBottom: '20px',
              }}
            >
              <p style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--accent)', marginBottom: '4px' }}>
                Estimated Impact
              </p>
              <p style={{ fontSize: '12px', color: 'var(--text-primary)', lineHeight: 1.5 }}>
                If all changes made: ~75% chance of recapturing this citation
              </p>
              <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                Time to implement: ~2 hours in Content Studio
              </p>
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <button
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  height: '30px',
                  padding: '0 12px',
                  borderRadius: '4px',
                  border: 'none',
                  background: 'var(--accent)',
                  color: 'var(--text-on-accent)',
                  fontSize: '12px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  fontFamily: 'var(--font-display)',
                  width: '100%',
                }}
              >
                <ArrowRight size={13} strokeWidth={1.5} />
              Update in Content Studio
              </button>
              <button
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  height: '30px',
                  padding: '0 12px',
                  borderRadius: '4px',
                  border: '1px solid var(--border)',
                  background: 'transparent',
                  color: 'var(--text-primary)',
                  fontSize: '12px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  fontFamily: 'var(--font-display)',
                  width: '100%',
                }}
              >
                <Plus size={13} strokeWidth={1.5} />
              Create competing piece
              </button>
              <button
                onClick={() => setRecaptureItem(null)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '30px',
                  padding: '0 12px',
                  borderRadius: '4px',
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--text-tertiary)',
                  fontSize: '12px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  fontFamily: 'var(--font-display)',
                  width: '100%',
                }}
              >
                Dismiss — Not a priority
              </button>
            </div>
          </div>
        )}
      </SlideDrawer>
    </>
  );
}
