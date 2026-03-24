'use client';

import { useState, useMemo } from 'react';
import { Card, Button, Badge } from '@/components/ui';
import type { Platform, Query } from '@/types';

interface SimulationProps {
  queries: Query[];
}

const PLATFORMS: { id: Platform; label: string }[] = [
  { id: 'chatgpt', label: 'ChatGPT' },
  { id: 'claude', label: 'Claude' },
  { id: 'perplexity', label: 'Perplexity' },
  { id: 'google_ai_overview', label: 'Google AI Overview' },
  { id: 'gemini', label: 'Gemini' },
];

const STRUCTURAL_SLIDERS = [
  { key: 'wordCount', label: 'Word Count', min: 500, max: 5000, step: 100, initial: 1500 },
  { key: 'headerCount', label: 'Headers', min: 0, max: 30, step: 1, initial: 8 },
  { key: 'listCount', label: 'Lists', min: 0, max: 20, step: 1, initial: 4 },
  { key: 'citationCount', label: 'Citations', min: 0, max: 30, step: 1, initial: 5 },
] as const;

function predictCPS(sliders: Record<string, number>, baseGap: number): Record<Platform, number> {
  const wf = Math.min(1, sliders.wordCount / 2000);
  const hf = Math.min(1, sliders.headerCount / 10);
  const lf = Math.min(1, sliders.listCount / 6);
  const cf = Math.min(1, sliders.citationCount / 8);
  const combined = wf * 0.3 + hf * 0.25 + lf * 0.2 + cf * 0.25;
  const base = 0.5 + combined * 0.4 - baseGap * 2;
  return {
    chatgpt: +Math.min(1, Math.max(0, base + 0.05)).toFixed(3),
    claude: +Math.min(1, Math.max(0, base + 0.02)).toFixed(3),
    perplexity: +Math.min(1, Math.max(0, base - 0.03)).toFixed(3),
    google_ai_overview: +Math.min(1, Math.max(0, base + 0.08)).toFixed(3),
    gemini: +Math.min(1, Math.max(0, base + 0.01)).toFixed(3),
  };
}

export function Simulation({ queries }: SimulationProps) {
  const [selectedQueries, setSelectedQueries] = useState<string[]>(queries.slice(0, 3).map((q) => q.id));
  const [draftContent, setDraftContent] = useState('');
  const [sliders, setSliders] = useState<Record<string, number>>(
    Object.fromEntries(STRUCTURAL_SLIDERS.map((s) => [s.key, s.initial]))
  );

  // Auto-detect structure from pasted content
  const autoDetected = useMemo(() => {
    if (!draftContent) return null;
    const words = draftContent.split(/\s+/).length;
    const headers = (draftContent.match(/^#{1,6}\s/gm) || []).length;
    const lists = (draftContent.match(/^[-*]\s/gm) || []).length;
    return { wordCount: words, headerCount: headers, listCount: lists, citationCount: 0 };
  }, [draftContent]);

  const activeSliders = autoDetected || sliders;

  const avgGap = useMemo(() => {
    const sel = queries.filter((q) => selectedQueries.includes(q.id));
    return sel.length ? sel.reduce((s, q) => s + q.gap, 0) / sel.length : 0.01;
  }, [queries, selectedQueries]);

  const predictions = useMemo(() => predictCPS(activeSliders, avgGap), [activeSliders, avgGap]);

  const toggleQuery = (id: string) => {
    setSelectedQueries((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Left: Configuration */}
      <div className="space-y-4">
        <Card hoverable={false}>
          <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">Content Input</h3>
          <textarea
            value={draftContent}
            onChange={(e) => setDraftContent(e.target.value)}
            placeholder="Paste URL or draft content (markdown supported)..."
            rows={6}
            className="w-full px-2 py-1.5 rounded-sm border border-border bg-bg text-[12px] text-text-primary outline-none focus:border-accent resize-none font-mono"
          />
          {autoDetected && (
            <div className="flex gap-3 mt-2 text-[10px] text-text-secondary">
              <span>Words: <span className="font-mono text-text-primary">{autoDetected.wordCount}</span></span>
              <span>Headers: <span className="font-mono text-text-primary">{autoDetected.headerCount}</span></span>
              <span>Lists: <span className="font-mono text-text-primary">{autoDetected.listCount}</span></span>
            </div>
          )}
        </Card>

        <Card hoverable={false}>
          <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">Target Queries</h3>
          <div className="max-h-[200px] overflow-y-auto space-y-0.5">
            {queries.slice(0, 25).map((q) => (
              <label key={q.id} className="flex items-center gap-2 p-1.5 rounded-sm hover:bg-accent-subtle cursor-pointer">
                <input type="checkbox" checked={selectedQueries.includes(q.id)} onChange={() => toggleQuery(q.id)} className="w-3 h-3 accent-[var(--accent)]" />
                <span className="text-[11px] text-text-primary truncate flex-1">{q.text}</span>
                <Badge variant={q.classification === 'significant_gap' ? 'error' : 'neutral'} className="shrink-0">{q.gap.toFixed(3)}</Badge>
              </label>
            ))}
          </div>
        </Card>

        {!autoDetected && (
          <Card hoverable={false}>
            <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">Structural Parameters</h3>
            <div className="space-y-3">
              {STRUCTURAL_SLIDERS.map((s) => (
                <div key={s.key}>
                  <div className="flex justify-between text-[10px] mb-1">
                    <span className="font-medium uppercase tracking-[0.06em] text-text-tertiary">{s.label}</span>
                    <span className="font-mono text-text-secondary">{sliders[s.key]}</span>
                  </div>
                  <input type="range" min={s.min} max={s.max} step={s.step} value={sliders[s.key]}
                    onChange={(e) => setSliders((prev) => ({ ...prev, [s.key]: +e.target.value }))}
                    className="w-full h-1 appearance-none bg-border rounded-full accent-[var(--accent)] cursor-pointer"
                  />
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>

      {/* Right: Predictions */}
      <div className="space-y-4">
        <Card hoverable={false}>
          <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">CPS Predictions</h3>
          <div className="space-y-3">
            {PLATFORMS.map((p) => {
              const score = predictions[p.id];
              return (
                <div key={p.id}>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-[11px] text-text-primary">{p.label}</span>
                    <span className="text-[12px] font-mono font-semibold text-text-primary">{score.toFixed(3)}</span>
                  </div>
                  <div className="w-full bg-border-subtle rounded-full h-[8px]">
                    <div className="h-[8px] rounded-full transition-all duration-300" style={{
                      width: `${score * 100}%`,
                      backgroundColor: score >= 0.7 ? 'var(--success)' : score >= 0.5 ? 'var(--accent)' : score >= 0.3 ? 'var(--warning)' : 'var(--error)',
                    }} />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <Card hoverable={false}>
          <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">Summary</h3>
          <div className="space-y-2">
            <div className="flex justify-between"><span className="text-[11px] text-text-secondary">Selected Queries</span><span className="text-[11px] font-mono text-text-primary">{selectedQueries.length}</span></div>
            <div className="flex justify-between"><span className="text-[11px] text-text-secondary">Average Gap</span><span className="text-[11px] font-mono text-text-primary">{avgGap.toFixed(4)}</span></div>
            <div className="flex justify-between"><span className="text-[11px] text-text-secondary">Avg CPS</span><span className="text-[11px] font-mono text-text-primary">{(Object.values(predictions).reduce((s, v) => s + v, 0) / 5).toFixed(3)}</span></div>
          </div>
          <Button variant="primary" className="w-full mt-4">Generate Content Brief</Button>
        </Card>
      </div>
    </div>
  );
}
