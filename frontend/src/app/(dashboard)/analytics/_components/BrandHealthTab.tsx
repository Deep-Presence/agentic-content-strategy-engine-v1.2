'use client';

import { useMemo } from 'react';
import { Card, Badge, ScoreGauge } from '@/components/ui';
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts';
import rawAudit from '@/../data/result-draft/artifacts/site_audit/lovable/039d53f8-cf4c-43c7-bae9-614ddd2cb472/audit_result.json';

interface RawAuditData {
  overall_score: number;
  grade: string;
  pages_crawled: number;
  total_findings: number;
  avg_snippet_readiness: number;
  pages_with_schema: number;
  avg_question_heading_ratio: number;
  dimension_scores: Array<{
    dimension: string;
    score: number;
    weight: number;
    weighted_score: number;
    finding_count: number;
    critical_count: number;
    high_count: number;
    medium_count: number;
    low_count: number;
  }>;
  ai_bot_access: Record<string, boolean | number | null>;
  top_findings: Array<{
    finding_type: string;
    dimension: string;
    severity: string;
    message: string;
    recommendation: string;
    count: number;
  }>;
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

export function BrandHealthTab() {
  const audit = rawAudit as unknown as RawAuditData;

  const radarData = useMemo(() => audit.dimension_scores.map((d) => ({
    dimension: DIM_NAMES[d.dimension] || d.dimension,
    score: Math.round(d.score),
    fullMark: 100,
  })), [audit.dimension_scores]);

  const aeoScore = Math.round(audit.avg_snippet_readiness * 10) / 10;

  const botEntries = useMemo(() => Object.entries(BOT_NAMES).map(([key, label]) => ({
    name: label,
    allowed: audit.ai_bot_access[key] === true,
  })), [audit.ai_bot_access]);

  // AEO readiness breakdown
  const aeoBreakdown = [
    { label: 'Snippet Readiness', value: `${aeoScore}%`, pct: aeoScore, target: 70 },
    { label: 'Structured Data Coverage', value: `${audit.pages_with_schema}/${audit.pages_crawled}`, pct: (audit.pages_with_schema / audit.pages_crawled) * 100, target: 90 },
    { label: 'Question-Heading Ratio', value: `${(audit.avg_question_heading_ratio * 100).toFixed(1)}%`, pct: audit.avg_question_heading_ratio * 100, target: 30 },
    { label: 'FAQ Section Rate', value: '34%', pct: 34, target: 50 },
    { label: 'Average Reading Level', value: 'Grade 8', pct: 75, target: 85 },
  ];

  // Sort findings by severity
  const sortedFindings = useMemo(() => {
    const order: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
    return [...audit.top_findings].sort((a, b) => (order[a.severity] ?? 5) - (order[b.severity] ?? 5));
  }, [audit.top_findings]);

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
                {/* Target marker */}
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
            <p>robots.txt: <span className="text-success font-medium">Present</span></p>
            <p>llms.txt: <span className="text-error font-medium">Missing</span></p>
          </div>
        </Card>
      </div>

      {/* Top Findings — severity-sorted cards */}
      <Card hoverable={false}>
        <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">
          Top Findings ({audit.total_findings} total)
        </h3>
        <div className="space-y-2">
          {sortedFindings.map((f, i) => (
            <div key={i} className="bg-bg border border-border rounded-md p-2.5 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant={f.severity === 'critical' ? 'error' : f.severity === 'high' ? 'warning' : f.severity === 'medium' ? 'info' : 'neutral'}>
                  {f.severity}
                </Badge>
                <Badge variant="neutral">{DIM_NAMES[f.dimension] || f.dimension}</Badge>
                <span className="text-[10px] font-mono text-text-tertiary ml-auto">{f.count} pages</span>
              </div>
              <p className="text-[12px] text-text-primary">{f.message}</p>
              <p className="text-[11px] text-text-secondary">{f.recommendation}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
