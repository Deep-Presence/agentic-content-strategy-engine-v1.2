'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';
import { WEBFLOW_SPA_SCORE } from '@/lib/data/webflow-fixtures';

interface SPAScoreHeroProps {
  score?: typeof WEBFLOW_SPA_SCORE;
}

function SemicircleGauge({ value, max = 30 }: { value: number; max?: number }) {
  const width = 220;
  const height = 130;
  const cx = width / 2;
  const cy = 110;
  const radius = 90;
  const startAngle = Math.PI;
  const endAngle = 0;

  // Zone boundaries as fractions of max
  const zones = [
    { start: 0, end: 8 / max, color: '#dc4a3a', label: 'Poor' },
    { start: 8 / max, end: 15 / max, color: '#e8913a', label: 'Moderate' },
    { start: 15 / max, end: 25 / max, color: '#788c5d', label: 'Good' },
    { start: 25 / max, end: 1, color: '#6a9bcc', label: 'Excellent' },
  ];

  const fraction = Math.min(value / max, 1);
  const currentZone = zones.find(
    (z) => fraction >= z.start && fraction < z.end
  ) || zones[zones.length - 1];

  function polarToCartesian(angleFraction: number) {
    const angle = startAngle - angleFraction * Math.PI;
    return {
      x: cx + radius * Math.cos(angle),
      y: cy - radius * Math.sin(angle),
    };
  }

  function describeArc(startFrac: number, endFrac: number) {
    const s = polarToCartesian(startFrac);
    const e = polarToCartesian(endFrac);
    const largeArc = endFrac - startFrac > 0.5 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${radius} ${radius} 0 ${largeArc} 1 ${e.x} ${e.y}`;
  }

  // Needle
  const needleAngle = startAngle - fraction * Math.PI;
  const needleLength = radius - 12;
  const needleTip = {
    x: cx + needleLength * Math.cos(needleAngle),
    y: cy - needleLength * Math.sin(needleAngle),
  };

  // Tick marks
  const ticks = [0, 8, 15, 25, 30];

  return (
    <div className="flex flex-col items-center">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        {/* Zone arcs */}
        {zones.map((zone, i) => (
          <path
            key={i}
            d={describeArc(zone.start, zone.end)}
            fill="none"
            stroke={zone.color}
            strokeWidth={14}
            strokeLinecap="butt"
            opacity={0.85}
          />
        ))}

        {/* Inner track for depth */}
        <path
          d={describeArc(0, 1)}
          fill="none"
          stroke="#e8e5de"
          strokeWidth={2}
          opacity={0.4}
        />

        {/* Tick marks and labels */}
        {ticks.map((tick) => {
          const frac = tick / max;
          const outerR = radius + 10;
          const innerR = radius + 3;
          const angle = startAngle - frac * Math.PI;
          const outer = {
            x: cx + outerR * Math.cos(angle),
            y: cy - outerR * Math.sin(angle),
          };
          const inner = {
            x: cx + innerR * Math.cos(angle),
            y: cy - innerR * Math.sin(angle),
          };
          const labelR = radius + 22;
          const label = {
            x: cx + labelR * Math.cos(angle),
            y: cy - labelR * Math.sin(angle),
          };
          return (
            <g key={tick}>
              <line
                x1={inner.x}
                y1={inner.y}
                x2={outer.x}
                y2={outer.y}
                stroke="#8a8880"
                strokeWidth={1.5}
              />
              <text
                x={label.x}
                y={label.y}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-stone-500"
                fontSize={10}
                fontFamily="system-ui, sans-serif"
              >
                {tick}
              </text>
            </g>
          );
        })}

        {/* Needle base circle */}
        <circle cx={cx} cy={cy} r={8} fill="#3a3935" />
        <circle cx={cx} cy={cy} r={5} fill="#faf9f5" />

        {/* Needle */}
        <line
          x1={cx}
          y1={cy}
          x2={needleTip.x}
          y2={needleTip.y}
          stroke="#3a3935"
          strokeWidth={2.5}
          strokeLinecap="round"
        />

        {/* Needle tip dot */}
        <circle cx={needleTip.x} cy={needleTip.y} r={3} fill="#d97757" />
      </svg>
      <div className="flex items-center gap-2 mt-1">
        <span
          className="inline-block w-2.5 h-2.5 rounded-full"
          style={{ backgroundColor: currentZone.color }}
        />
        <span className="text-sm font-medium text-stone-600">
          {currentZone.label} Range
        </span>
      </div>
    </div>
  );
}

export function SPAScoreHero({ score = WEBFLOW_SPA_SCORE }: SPAScoreHeroProps) {
  const delta = score.mean_company_similarity - score.mean_citation_similarity;
  const deltaPercent = Math.abs(
    (delta / score.mean_citation_similarity) * 100
  ).toFixed(1);
  const isNegativeDelta = delta < 0;

  return (
    <Card className="relative overflow-hidden border-ocean-200/60 bg-white shadow-sm">
      {/* Subtle gradient accent along top */}
      <div className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-ocean-300 via-ocean-400 to-ocean-300" />

      <CardContent className="pt-7 pb-6 px-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-center">
          {/* Left: Score Display */}
          <div className="flex flex-col items-center md:items-start">
            <p className="text-[3.5rem] leading-none font-serif font-semibold tracking-tight text-stone-900">
              {score.score.toFixed(3)}
            </p>
            <p className="mt-2 text-sm font-medium text-stone-500 uppercase tracking-wider">
              Semantic Proximity
            </p>
            <p className="text-sm font-medium text-stone-500 uppercase tracking-wider">
              Analysis Score
            </p>
            <div className="mt-3 flex items-center gap-2">
              <span className="text-xs text-stone-400">
                {score.total_queries} queries
              </span>
              <span className="text-stone-300">&middot;</span>
              <span className="text-xs text-stone-400">
                {score.total_citations.toLocaleString()} citations
              </span>
            </div>
          </div>

          {/* Center: Gauge */}
          <div className="flex justify-center">
            <SemicircleGauge value={score.score} />
          </div>

          {/* Right: Stats */}
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-4">
              <span className="text-sm text-stone-500">
                Mean Citation Similarity
              </span>
              <span className="text-sm font-semibold font-mono text-stone-800">
                {score.mean_citation_similarity.toFixed(4)}
              </span>
            </div>

            <div className="flex items-center justify-between gap-4">
              <span className="text-sm text-stone-500">
                Mean Company Similarity
              </span>
              <span className="text-sm font-semibold font-mono text-stone-800">
                {score.mean_company_similarity.toFixed(4)}
              </span>
            </div>

            <div className="h-px bg-stone-200 my-1" />

            <div className="flex items-center justify-between gap-4">
              <span className="text-sm text-stone-500">Delta</span>
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    'text-sm font-semibold font-mono',
                    isNegativeDelta ? 'text-red-600' : 'text-sage-600'
                  )}
                >
                  {delta > 0 ? '+' : ''}
                  {delta.toFixed(4)}
                </span>
              </div>
            </div>

            {isNegativeDelta && (
              <p className="text-xs text-red-500 leading-snug">
                Citations outperform by {deltaPercent}%
              </p>
            )}

            <div className="h-px bg-stone-200 my-1" />

            <div className="flex items-center justify-between gap-4">
              <span className="text-sm text-stone-500">p-value</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold font-mono text-stone-800">
                  &lt; 0.0001
                </span>
                <Badge variant="success" className="text-[10px] px-1.5 py-0">
                  Statistically Significant
                </Badge>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
