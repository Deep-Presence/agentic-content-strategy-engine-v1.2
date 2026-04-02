'use client';

import type { ContentPiece, LifecycleStage } from './data';

const STAGE_CONFIG: Record<LifecycleStage, { label: string; color: string }> = {
  growing: { label: 'Growing', color: '#6CB8D2' },
  peaking: { label: 'Peaking', color: '#F5A623' },
  stable: { label: 'Stable', color: 'var(--text-tertiary)' },
  declining: { label: 'Declining', color: '#E87C3F' },
  stale: { label: 'Stale', color: '#E5484D' },
};

const STAGES: LifecycleStage[] = ['growing', 'peaking', 'stable', 'declining', 'stale'];

interface LifecycleDistributionProps {
  pieces: ContentPiece[];
}

export function LifecycleDistribution({ pieces }: LifecycleDistributionProps) {
  const counts = STAGES.map((s) => ({
    stage: s,
    count: pieces.filter((p) => p.lifecycle === s).length,
  }));
  const maxCount = Math.max(...counts.map((c) => c.count), 1);

  return (
    <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: 4, padding: 12 }}>
      <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
        Content Lifecycle Distribution
      </h3>
      <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2, marginBottom: 12 }}>
        How many pieces are in each lifecycle stage
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {counts.map(({ stage, count }) => {
          const cfg = STAGE_CONFIG[stage];
          return (
            <div key={stage} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 13, color: 'var(--text-primary)', width: 80, flexShrink: 0 }}>
                {cfg.label}
              </span>
              <div style={{ flex: 1, height: 20, borderRadius: 4, background: 'var(--border)', overflow: 'hidden', position: 'relative' }}>
                <div style={{
                  width: `${(count / maxCount) * 100}%`,
                  height: '100%', borderRadius: 4,
                  background: cfg.color,
                  minWidth: count > 0 ? 8 : 0,
                  transition: 'width 0.3s ease',
                }} />
              </div>
              <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)', width: 60 }}>
                {count} piece{count !== 1 ? 's' : ''}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
