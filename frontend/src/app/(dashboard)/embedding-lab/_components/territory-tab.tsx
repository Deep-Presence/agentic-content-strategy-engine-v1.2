'use client';

import { useState, useCallback } from 'react';
import { TerritoryMap } from './territory-map';
import { getClusterDataForEngine, ENGINE_KEYS, ENGINE_META } from './data';
import type { EngineKey } from './data';
import { BrandLogo } from './brand-logo';

interface TerritoryTabProps {
  onClusterSelect: (clusterId: string) => void;
}

export function TerritoryTab({ onClusterSelect }: TerritoryTabProps) {
  const [selectedCluster, setSelectedCluster] = useState<string | null>(null);
  const [engineFilter, setEngineFilter] = useState<EngineKey | 'all'>('all');
  const [viewMode, setViewMode] = useState<'citations' | 'market_share' | 'authority'>('citations');

  const clusters = getClusterDataForEngine(engineFilter);

  const handleClusterSelect = useCallback((id: string | null) => {
    setSelectedCluster(id);
    if (id) onClusterSelect(id);
  }, [onClusterSelect]);

  return (
    <div className="space-y-3" style={{ animation: 'fadeIn 150ms ease-out' }}>
      {/* Controls row */}
      <div className="flex items-center justify-between gap-3">
        {/* Engine toggle */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-text-tertiary">View:</span>
          <div className="flex items-center gap-1 border border-border rounded p-0.5">
            <button
              onClick={() => setEngineFilter('all')}
              className={`px-2.5 h-[26px] text-[11px] font-medium rounded transition-colors cursor-pointer ${
                engineFilter === 'all'
                  ? 'bg-accent text-text-on-accent'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              All Engines
            </button>
            {ENGINE_KEYS.map((key) => (
              <button
                key={key}
                onClick={() => setEngineFilter(key)}
                className={`flex items-center gap-1.5 px-2 h-[26px] text-[11px] font-medium rounded transition-colors cursor-pointer ${
                  engineFilter === key
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

        <div className="flex items-center gap-3">
          {selectedCluster && (
            <button
              onClick={() => setSelectedCluster(null)}
              className="text-[11px] text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
            >
              Reset View
            </button>
          )}

          {/* View mode toggle */}
          <div className="flex items-center gap-1 border border-border rounded p-0.5">
            {(['citations', 'market_share', 'authority'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-2.5 h-[26px] text-[11px] font-medium rounded transition-colors cursor-pointer ${
                  viewMode === mode
                    ? 'bg-accent text-text-on-accent'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                {mode === 'citations' ? 'Size by Citations' : mode === 'market_share' ? 'Size by Market Share' : 'Color by Authority'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Map container — full width, fixed height */}
      <div className="border border-border rounded-md overflow-hidden" style={{ height: 'calc(100vh - 200px)', minHeight: 500 }}>
        <TerritoryMap
          clusters={clusters}
          engineFilter={engineFilter}
          viewMode={viewMode}
          onClusterSelect={handleClusterSelect}
          selectedCluster={selectedCluster}
        />
      </div>
    </div>
  );
}
