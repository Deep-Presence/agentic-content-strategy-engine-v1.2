'use client';

import { useState } from 'react';
import { TOTAL_TERRITORIES, DANGER_ZONES, CRITICAL_GAPS, TOTAL_COMPETITORS } from './_components/data';
import { TerritoryTab } from './_components/territory-tab';
import { GapIntelligenceTab } from './_components/gap-intelligence-tab';
import { EngineIntelligenceTab } from './_components/engine-intelligence-tab';
import { EmbeddingSpaceTab } from './_components/embedding-space-tab';
import { LayoutGrid, BarChart3, Globe, ScatterChart } from 'lucide-react';

type Tab = 'territory' | 'gap' | 'engine' | 'embedding';

const TABS: { id: Tab; label: string; icon: typeof LayoutGrid }[] = [
  { id: 'territory', label: 'Territory Map', icon: LayoutGrid },
  { id: 'gap', label: 'Gap Intelligence', icon: BarChart3 },
  { id: 'engine', label: 'Engine Intelligence', icon: Globe },
  { id: 'embedding', label: 'Embedding Space', icon: ScatterChart },
];

const STATS = [
  { value: TOTAL_TERRITORIES, label: 'TERRITORIES', color: 'var(--text-primary)' },
  { value: DANGER_ZONES, label: 'DANGER ZONES', color: 'var(--error)' },
  { value: CRITICAL_GAPS, label: 'CRITICAL GAPS', color: 'var(--warning)' },
  { value: TOTAL_COMPETITORS, label: 'COMPETITORS', color: 'var(--text-primary)' },
];

export default function EmbeddingLabPage() {
  const [activeTab, setActiveTab] = useState<Tab>('territory');

  return (
    <div className="space-y-3">
      {/* Page Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[22px] font-semibold text-text-primary tracking-[-0.02em] font-display">
            Embedding Lab
          </h1>
          <p className="text-[13px] text-text-secondary mt-0.5">
            Competitive territory intelligence powered by semantic analysis
          </p>
        </div>
        <div className="flex items-center gap-4">
          {STATS.map((stat) => (
            <div key={stat.label} className="text-right">
              <span className="text-[13px] font-mono font-semibold" style={{ color: stat.color }}>
                {stat.value}
              </span>
              <span className="text-[10px] uppercase tracking-[0.06em] text-text-tertiary ml-1">
                {stat.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center gap-0 border-b border-border">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-4 h-[36px] text-[13px] font-medium border-b-2 -mb-[1px] transition-colors cursor-pointer ${
                activeTab === tab.id
                  ? 'border-accent text-accent font-semibold'
                  : 'border-transparent text-text-secondary hover:text-text-primary'
              }`}
            >
              <Icon size={14} strokeWidth={1.5} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      {activeTab === 'territory' && <TerritoryTab />}
      {activeTab === 'gap' && <GapIntelligenceTab />}
      {activeTab === 'engine' && <EngineIntelligenceTab />}
      {activeTab === 'embedding' && <EmbeddingSpaceTab />}
    </div>
  );
}
