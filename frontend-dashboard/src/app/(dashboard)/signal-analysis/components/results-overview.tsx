'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Dna } from 'lucide-react';
import { SpaScoreDisplay } from './spa-score-display';
import { ClusterCard } from './cluster-card';
import { GapBriefTable } from './gap-brief-table';
import type { GapReport } from '@/types/gap-analysis';

interface ResultsOverviewProps {
  report: GapReport;
  companySlug: string;
  className?: string;
}

export function ResultsOverview({ report, companySlug, className }: ResultsOverviewProps) {
  const [selectedCluster, setSelectedCluster] = useState<string | null>(null);

  return (
    <div className={className}>
      {/* SPA Score Hero */}
      <section className="mb-8">
        <SpaScoreDisplay
          spa={report.spa_score}
          totalQueries={report.total_queries}
          totalCitations={report.total_citations}
          executiveSummary={report.executive_summary}
        />
      </section>

      {/* Cluster Breakdown */}
      <section className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif text-heading-2 font-semibold text-cream-950">
            Cluster Breakdown
          </h2>
          <Link
            href={`/embedding-lab?company=${companySlug}`}
            className="inline-flex items-center gap-1.5 text-body-sm font-sans text-ocean-500 hover:text-ocean-600 transition-colors"
          >
            <Dna className="h-3.5 w-3.5" />
            Open in Embedding Lab
          </Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {report.clusters.map((cluster) => (
            <ClusterCard
              key={cluster.cluster_id}
              cluster={cluster}
              isSelected={selectedCluster === cluster.cluster_id}
              onClick={() =>
                setSelectedCluster((prev) =>
                  prev === cluster.cluster_id ? null : cluster.cluster_id
                )
              }
            />
          ))}
        </div>
      </section>

      {/* Gap Briefs Table */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif text-heading-2 font-semibold text-cream-950">
            Top Gap Briefs
          </h2>
          <span className="text-body-sm font-sans text-cream-600">
            {report.top_gaps.length} briefs ranked by gap severity
          </span>
        </div>
        <GapBriefTable
          briefs={report.top_gaps}
          clusters={report.clusters.map((c) => ({
            cluster_id: c.cluster_id,
            cluster_name: c.cluster_name,
          }))}
          selectedCluster={selectedCluster}
          onClusterChange={setSelectedCluster}
        />
        <div className="mt-4 text-center">
          <Link
            href={`/embedding-lab?company=${companySlug}`}
            className="inline-flex items-center gap-1.5 text-body-sm font-sans text-ocean-500 hover:text-ocean-600 transition-colors"
          >
            <Dna className="h-3.5 w-3.5" />
            Open in Embedding Lab for full visualization
          </Link>
        </div>
      </section>
    </div>
  );
}
