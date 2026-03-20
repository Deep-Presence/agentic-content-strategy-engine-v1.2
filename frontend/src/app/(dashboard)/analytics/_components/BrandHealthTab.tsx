'use client';

import { useMemo } from 'react';
import { Card, Badge, ScoreGauge, Skeleton } from '@/components/ui';
import { useSiteAuditLatest } from '@/lib/hooks/useSiteAudit';
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts';

interface BrandHealthTabProps {
  slug: string;
}

const DIM_NAMES: Record<string, string> = {
  crawlability: 'Crawlability', performance: 'Performance', on_page_seo: 'On-Page SEO',
  extractability: 'Extractability', schema_markup: 'Schema', eeat: 'E-E-A-T',
  freshness: 'Freshness', security: 'Security',
};

const BOT_NAMES: Record<string, string> = {
  gptbot_allowed: 'GPTBot (OpenAI)', claudebot_allowed: 'ClaudeBot (Anthropic)',
  perplexitybot_allowed: 'PerplexityBot', google_extended_allowed: 'Google-Extended',
  ccbot_allowed: 'CCBot (Common Crawl)',
};

export function BrandHealthTab({ slug }: BrandHealthTabProps) {
  const { audit, isLoading } = useSiteAuditLatest(slug);

  const radarData = useMemo(() => {
    if (!audit) return [];
    return audit.dimension_scores.map((d) => ({
      dimension: DIM_NAMES[d.dimension] || d.dimension,
      score: Math.round(d.score),
      fullMark: 100,
    }));
  }, [audit]);

  const botEntries = useMemo(() => {
    if (!audit) return [];
    const access = audit.ai_bot_access;
    return Object.entries(BOT_NAMES).map(([key, label]) => ({
      name: label,
      allowed: access[key as keyof typeof access] === true,
    }));
  }, [audit]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-[350px] rounded-md" />
          <Skeleton className="h-[350px] rounded-md" />
        </div>
        <Skeleton className="h-[200px] rounded-md" />
      </div>
    );
  }

  if (!audit) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-[14px] text-text-secondary mb-2">No site audit data yet</p>
        <p className="text-[12px] text-text-tertiary">Run a site audit pipeline to see brand health metrics here.</p>
      </div>
    );
  }

  const aeoScore = Math.round(audit.avg_snippet_readiness * 10) / 10;

  const aeoBreakdown = [
    { label: 'Snippet Readiness', value: `${aeoScore}%`, pct: aeoScore, target: 70 },
    { label: 'Structured Data Coverage', value: `${audit.pages_with_schema}/${audit.pages_crawled}`, pct: (audit.pages_with_schema / Math.max(audit.pages_crawled, 1)) * 100, target: 90 },
    { label: 'Question-Heading Ratio', value: `${(audit.avg_question_heading_ratio * 100).toFixed(1)}%`, pct: audit.avg_question_heading_ratio * 100, target: 30 },
  ];

  return (
    <div className="space-y-4">
      {/* Row 1: AEO Score Gauge + Radar */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card hoverable={false}>
          <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-4">AEO Readiness Score</h3>
          <div className="flex flex-col items-center">
            <ScoreGauge score={aeoScore} max={100} size={160} />
            <p className="text-[11px] text-text-secondary mt-3">Based on {audit.pages_crawled} pages crawled</p>
            <div className="grid grid-cols-2 gap-3 mt-4 w-full">
              <div className="bg-bg border border-border rounded-md p-2.5">
                <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Overall Score</p>
                <p className="font-display text-[16px] font-semibold text-text-primary mt-0.5">{audit.overall_score.toFixed(1)}</p>
              </div>
              <div className="bg-bg border border-border rounded-md p-2.5">
                <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Grade</p>
                <p className="font-display text-[16px] font-semibold text-success mt-0.5">{audit.grade}</p>
              </div>
            </div>
          </div>
        </Card>

        <Card hoverable={false}>
          <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-4">Dimension Scores</h3>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 10, fill: 'var(--text-secondary)' }} />
              <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 9, fill: 'var(--text-tertiary)' }} />
              <Radar dataKey="score" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.2} strokeWidth={2} />
            </RadarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* AEO Readiness Breakdown (Progress Bars) */}
      <Card hoverable={false}>
        <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">AEO Readiness Breakdown</h3>
        <div className="space-y-3">
          {aeoBreakdown.map((item) => (
            <div key={item.label}>
              <div className="flex justify-between items-center mb-1">
                <span className="text-[11px] text-text-primary">{item.label}</span>
                <span className="text-[11px] font-mono text-text-secondary">{item.value}</span>
              </div>
              <div className="relative w-full bg-border-subtle rounded-full h-[8px]">
                <div
                  className="h-[8px] rounded-full transition-all"
                  style={{
                    width: `${Math.min(100, item.pct)}%`,
                    backgroundColor: item.pct >= item.target ? 'var(--success)' : item.pct >= item.target * 0.6 ? 'var(--warning)' : 'var(--error)',
                  }}
                />
                <div
                  className="absolute top-0 h-[8px] w-[2px] bg-text-tertiary"
                  style={{ left: `${item.target}%` }}
                  title={`Target: ${item.target}%`}
                />
              </div>
              <p className="text-[9px] text-text-tertiary mt-0.5">Target: {item.target}%</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Row 2: Dimension Table + Bot Access */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card hoverable={false}>
          <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">Dimension Breakdown</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  {['Dimension', 'Score', 'Weight', 'Weighted', 'Findings'].map((h) => (
                    <th key={h} className="text-left p-[6px_10px] text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {audit.dimension_scores.map((dim) => (
                  <tr key={dim.dimension} className="border-b border-border-subtle hover:bg-accent-subtle transition-colors">
                    <td className="p-[6px_10px] text-[12px] text-text-primary">{DIM_NAMES[dim.dimension] || dim.dimension}</td>
                    <td className="p-[6px_10px]">
                      <Badge variant={dim.score >= 95 ? 'success' : dim.score >= 80 ? 'info' : 'warning'}>{dim.score.toFixed(1)}</Badge>
                    </td>
                    <td className="p-[6px_10px] text-[12px] font-mono text-text-secondary">{(dim.weight * 100).toFixed(0)}%</td>
                    <td className="p-[6px_10px] text-[12px] font-mono text-text-primary">{dim.weighted_score.toFixed(2)}</td>
                    <td className="p-[6px_10px] text-[12px] font-mono text-text-secondary">{dim.finding_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card hoverable={false}>
          <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">AI Bot Access</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left p-[6px_10px] text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Bot</th>
                  <th className="text-center p-[6px_10px] text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Status</th>
                </tr>
              </thead>
              <tbody>
                {botEntries.map((b) => (
                  <tr key={b.name} className="border-b border-border-subtle">
                    <td className="p-[6px_10px] text-[12px] text-text-primary">{b.name}</td>
                    <td className="p-[6px_10px] text-center">
                      <Badge variant={b.allowed ? 'success' : 'error'}>{b.allowed ? 'Allowed' : 'Blocked'}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3 space-y-1 text-[11px] text-text-secondary">
            <p>robots.txt: <span className={audit.ai_bot_access.robots_txt_exists ? 'text-success' : 'text-error'} style={{ fontWeight: 500 }}>{audit.ai_bot_access.robots_txt_exists ? 'Present' : 'Missing'}</span></p>
            <p>llms.txt: <span className={audit.ai_bot_access.has_llms_txt ? 'text-success' : 'text-error'} style={{ fontWeight: 500 }}>{audit.ai_bot_access.has_llms_txt ? 'Present' : 'Missing'}</span></p>
          </div>
        </Card>
      </div>

      {/* Findings summary */}
      <Card hoverable={false}>
        <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">
          Findings Summary ({audit.total_findings} total)
        </h3>
        <div className="flex gap-3 flex-wrap">
          {Object.entries(audit.findings_by_severity).map(([severity, count]) => (
            <div key={severity} className="bg-bg border border-border rounded-md p-2.5 flex items-center gap-2">
              <Badge variant={severity === 'critical' ? 'error' : severity === 'high' ? 'warning' : severity === 'medium' ? 'info' : 'neutral'}>
                {severity}
              </Badge>
              <span className="text-[14px] font-mono font-semibold text-text-primary">{count}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
