'use client';

import { useState } from 'react';
import { ENGINE_DATA, ENGINE_KEYS, ENGINE_META, DIVERGENCE_DATA, getClusterDataForEngine } from './data';
import type { EngineKey } from './data';
import { BrandLogo } from './brand-logo';
import { TerritoryMap } from './territory-map';

export function EngineIntelligenceTab() {
  const [engineView, setEngineView] = useState<EngineKey | 'all'>('all');

  return (
    <div className="space-y-4" style={{ animation: 'fadeIn 150ms ease-out' }}>
      {/* Engine Comparison Grid */}
      <div>
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-3">
          Engine Comparison
        </h3>
        <div className="grid grid-cols-5 gap-3">
          {ENGINE_DATA.map((engine) => (
            <div key={engine.key} className="border border-border rounded-md p-3 space-y-3">
              <div className="flex items-center gap-2">
                <BrandLogo domain={engine.domain} size={16} />
                <span className="text-[13px] font-semibold text-text-primary font-display">{engine.label}</span>
              </div>
              <div>
                <span className="text-[24px] font-mono font-semibold text-text-primary">{engine.totalCitations}</span>
                <span className="text-[11px] text-text-tertiary ml-1">citations</span>
              </div>
              <div className="text-[12px]">
                <div className="text-text-tertiary">Top domain:</div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <BrandLogo domain={engine.topDomain} size={12} />
                  <span className="text-text-primary font-medium truncate">{engine.topDomain}</span>
                </div>
              </div>
              <div className="text-[12px]">
                <div className="text-text-tertiary">Unique citations</div>
                <div className="font-mono font-semibold text-text-primary">
                  {engine.uniqueCitations} <span className="text-text-tertiary font-normal">(not on other engines)</span>
                </div>
              </div>
              <div className="text-[12px]">
                <div className="text-text-tertiary mb-1">Preferred:</div>
                <div className="flex flex-wrap gap-1">
                  {engine.preferredTraits.map(t => (
                    <span key={t} className="text-[10px] px-1.5 py-0.5 rounded border border-border text-text-secondary">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Engine Divergence Table */}
      <div className="border border-border rounded-md overflow-hidden">
        <div className="px-3 py-2 border-b border-border bg-surface">
          <h3 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary">
            Engine Divergence — Queries where engines disagree on citations
          </h3>
        </div>
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary">Query</th>
              {ENGINE_KEYS.map(key => (
                <th key={key} className="text-center px-2 py-2 text-[10px] font-semibold uppercase tracking-[0.06em]" style={{ color: ENGINE_META[key].color }}>
                  {ENGINE_META[key].label}
                </th>
              ))}
              <th className="text-center px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary">Agreement</th>
            </tr>
          </thead>
          <tbody>
            {[...DIVERGENCE_DATA].sort((a, b) => a.agreement - b.agreement).map((row, idx) => {
              const agreeColor = row.agreement < 33 ? 'var(--error)' : row.agreement < 60 ? 'var(--warning)' : 'var(--success)';
              return (
                <tr
                  key={idx}
                  className="border-b border-border-subtle hover:bg-surface transition-colors"
                  style={{ animation: `fadeUp 300ms ease-out ${idx * 25}ms both` }}
                >
                  <td className="px-3 py-1.5 max-w-[240px]">
                    <span className="text-[12px] text-text-primary truncate block">{row.query}</span>
                  </td>
                  {ENGINE_KEYS.map(key => {
                    const domain = row.engines[key];
                    return (
                      <td key={key} className="px-2 py-1.5 text-center">
                        {domain ? (
                          <div className="flex items-center justify-center gap-1">
                            <BrandLogo domain={domain} size={12} />
                            <span className="text-[11px] text-text-secondary truncate max-w-[80px]">
                              {domain.replace('www.', '')}
                            </span>
                          </div>
                        ) : (
                          <span className="text-[11px] text-text-tertiary">—</span>
                        )}
                      </td>
                    );
                  })}
                  <td className="px-3 py-1.5 text-center">
                    <span className="font-mono text-[12px] font-semibold" style={{ color: agreeColor }}>
                      {row.agreement}%
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Per-Engine Territory Map */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <span className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary">Per-Engine Territory:</span>
          <div className="flex items-center gap-1 border border-border rounded p-0.5">
            <button
              onClick={() => setEngineView('all')}
              className={`px-2.5 h-[26px] text-[11px] font-medium rounded transition-colors cursor-pointer ${
                engineView === 'all'
                  ? 'bg-accent text-text-on-accent'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              All Engines
            </button>
            {ENGINE_KEYS.map((key) => (
              <button
                key={key}
                onClick={() => setEngineView(key)}
                className={`flex items-center gap-1.5 px-2 h-[26px] text-[11px] font-medium rounded transition-colors cursor-pointer ${
                  engineView === key
                    ? 'bg-accent text-text-on-accent'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                <BrandLogo domain={ENGINE_META[key].domain} size={12} />
                {ENGINE_META[key].label}
              </button>
            ))}
          </div>
        </div>
        <div className="border border-border rounded-md overflow-hidden" style={{ height: 420 }}>
          <TerritoryMap
            clusters={getClusterDataForEngine(engineView)}
            engineFilter={engineView}
            viewMode="citations"
            onClusterSelect={() => {}}
            selectedCluster={null}
          />
        </div>
      </div>
    </div>
  );
}
