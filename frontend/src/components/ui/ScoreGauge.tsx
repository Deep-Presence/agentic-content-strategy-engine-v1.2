import { cn } from '@/lib/utils';

interface ScoreGaugeProps {
  score: number;
  max?: number;
  size?: number;
  className?: string;
}

export function ScoreGauge({ score, max = 100, size = 80, className }: ScoreGaugeProps) {
  const pct = Math.min(1, Math.max(0, score / max));
  const radius = 36;
  const circumference = Math.PI * radius;
  const offset = circumference * (1 - pct);

  return (
    <div className={cn('relative inline-flex items-center justify-center', className)} style={{ width: size, height: size * 0.65 }}>
      <svg viewBox="0 0 80 52" width={size} height={size * 0.65}>
        {/* Background arc */}
        <path
          d="M 4,48 A 36,36 0 0 1 76,48"
          fill="none"
          stroke="var(--border)"
          strokeWidth="6"
          strokeLinecap="round"
        />
        {/* Value arc */}
        <path
          d="M 4,48 A 36,36 0 0 1 76,48"
          fill="none"
          stroke="var(--accent)"
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-700 ease-out"
        />
      </svg>
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-center">
        <span className="font-display text-[16px] font-semibold text-text-primary">{score}</span>
      </div>
    </div>
  );
}
