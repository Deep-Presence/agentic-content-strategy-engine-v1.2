'use client';

import { useCountUp } from '@/lib/hooks/use-count-up';

interface HeroHealthBarProps {
  citabilityScore: number;
  spaScore: number;
  totalQueries: number;
  totalCitations: number;
  publishedCount: number;
  gapCount: number;
}

function AnimatedMetric({
  value,
  suffix,
  label,
  color,
  decimals = 0,
  delay,
}: {
  value: number;
  suffix?: string;
  label: string;
  color: string;
  decimals?: number;
  delay: number;
}) {
  const animated = useCountUp(value, { decimals });

  return (
    <div
      className="animate-fade-in-up text-center"
      style={{ animationDelay: `${delay}s` }}
    >
      <p className={`font-serif text-heading-1 font-semibold ${color}`}>
        {decimals > 0 ? animated.toFixed(decimals) : animated.toLocaleString()}
        {suffix}
      </p>
      <p className="text-caption font-sans text-cream-600 mt-0.5">{label}</p>
    </div>
  );
}

function SemiCircleGauge({ score }: { score: number }) {
  const radius = 56;
  const cx = 70;
  const cy = 65;
  const halfCircumference = Math.PI * radius; // ~175.93
  const offset = halfCircumference * (1 - score / 100);

  const gaugeColor = score < 50 ? '#c44040' : score < 75 ? '#e8926d' : '#788c5d';
  const animatedScore = useCountUp(score, { duration: 1400 });

  return (
    <div className="flex flex-col items-center animate-fade-in-scale" style={{ animationDelay: '0.2s' }}>
      <svg width="140" height="80" viewBox="0 0 140 80" className="overflow-visible">
        {/* Background arc */}
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke="#efeee8"
          strokeWidth="10"
          strokeDasharray={`${halfCircumference} ${halfCircumference}`}
          strokeLinecap="round"
          transform={`rotate(180 ${cx} ${cy})`}
        />
        {/* Foreground arc */}
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke={gaugeColor}
          strokeWidth="10"
          strokeDasharray={`${halfCircumference} ${halfCircumference}`}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(180 ${cx} ${cy})`}
          style={{ transition: 'stroke-dashoffset 1.4s ease-out' }}
        />
      </svg>
      <div className="relative -mt-12 text-center">
        <p className="font-serif text-[2rem] leading-none font-semibold" style={{ color: gaugeColor }}>
          {animatedScore}%
        </p>
        <p className="text-micro font-sans text-cream-600 mt-0.5">AI Visibility</p>
      </div>
    </div>
  );
}

export function HeroHealthBar({
  citabilityScore,
  spaScore,
  totalQueries,
  totalCitations,
  publishedCount,
  gapCount,
}: HeroHealthBarProps) {
  return (
    <div className="bg-gradient-to-br from-cream-50 to-cream-200 border border-[var(--border-default)] rounded-md shadow-sm overflow-hidden">
      <div className="px-6 py-5">
        <div className="flex items-center justify-between gap-8">
          {/* Metrics grid */}
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-6 flex-1">
            <AnimatedMetric value={citabilityScore} suffix="%" label="AI Visibility" color="text-error" delay={0} />
            <AnimatedMetric value={spaScore} label="SPA Score" color="text-ocean-500" decimals={1} delay={0.08} />
            <AnimatedMetric value={totalQueries} label="Queries" color="text-cream-950" delay={0.16} />
            <AnimatedMetric value={totalCitations} label="Citations" color="text-cream-950" delay={0.24} />
            <AnimatedMetric value={publishedCount} suffix="" label="Published" color="text-sage-400" delay={0.32} />
            <AnimatedMetric value={gapCount} label="Gaps Found" color="text-terracotta-400" delay={0.4} />
          </div>

          {/* Semicircle gauge — hidden on small screens */}
          <div className="hidden lg:block shrink-0">
            <SemiCircleGauge score={citabilityScore} />
          </div>
        </div>
      </div>
      {/* Terracotta accent line */}
      <div className="h-0.5 bg-terracotta-400" />
    </div>
  );
}
