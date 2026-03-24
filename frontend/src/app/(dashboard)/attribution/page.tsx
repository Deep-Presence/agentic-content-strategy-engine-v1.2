'use client';

import { useState, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { MetricCard } from '@/components/ui';
import type { Platform } from '@/types';
import { PlatformFilter } from './_components/PlatformFilter';
import { AttributionFunnel } from './_components/AttributionFunnel';
import { ROITable } from './_components/ROITable';
import { IntegrationStatusCards } from './_components/IntegrationStatusCards';
import {
  kpis,
  funnelStepsAll,
  getFunnelForPlatform,
  getKpisForPlatform,
  roiTableData,
} from './_components/data';

const RevenueDonutChart = dynamic(
  () => import('./_components/RevenueDonutChart').then((mod) => mod.RevenueDonutChart),
  { ssr: false }
);

const PlatformBarChart = dynamic(
  () => import('./_components/PlatformBarChart').then((mod) => mod.PlatformBarChart),
  { ssr: false }
);

const TrendChart = dynamic(
  () => import('./_components/TrendChart').then((mod) => mod.TrendChart),
  { ssr: false }
);

const ConversionPathChart = dynamic(
  () => import('./_components/ConversionPathChart').then((mod) => mod.ConversionPathChart),
  { ssr: false }
);

export default function AttributionPage() {
  const [platform, setPlatform] = useState<Platform | 'all'>('all');

  const activeKpis = useMemo(
    () => (platform === 'all' ? kpis : getKpisForPlatform(platform)),
    [platform]
  );

  const activeFunnel = useMemo(
    () => (platform === 'all' ? funnelStepsAll : getFunnelForPlatform(platform)),
    [platform]
  );

  return (
    <div className="space-y-5">
      {/* Demo Banner */}
      <div className="bg-accent-subtle border border-border rounded-md p-3 flex items-center justify-between">
        <span className="text-[13px] text-text-secondary">
          Demo data shown. Connect your CRM and analytics to see real attribution.
        </span>
        <a href="/settings?tab=integrations" className="text-[13px] text-accent hover:underline font-medium">
          Connect Integrations →
        </a>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {activeKpis.map((kpi) => (
          <MetricCard
            key={kpi.label}
            label={kpi.label}
            value={kpi.value}
            delta={kpi.delta}
            deltaType={kpi.deltaType}
          />
        ))}
      </div>

      {/* Platform Filter */}
      <PlatformFilter selected={platform} onChange={setPlatform} />

      {/* Attribution Funnel */}
      <div className="bg-surface border border-border rounded-md p-[14px]">
        <h3 className="text-[18px] font-semibold text-text-primary mb-4">
          Attribution Funnel
        </h3>
        <AttributionFunnel steps={activeFunnel} />
      </div>

      {/* Charts Row 1: Donut + Bar */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <RevenueDonutChart />
        <PlatformBarChart />
      </div>

      {/* Charts Row 2: Trend + Conversion Path */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <TrendChart />
        <ConversionPathChart />
      </div>

      {/* Content ROI Table */}
      <div className="bg-surface border border-border rounded-md p-[14px]">
        <h3 className="text-[18px] font-semibold text-text-primary mb-3">
          Content ROI
        </h3>
        <ROITable data={roiTableData} />
      </div>

      {/* Integration Status */}
      <div>
        <h3 className="text-[18px] font-semibold text-text-primary mb-3">
          Integration Status
        </h3>
        <IntegrationStatusCards />
      </div>
    </div>
  );
}
