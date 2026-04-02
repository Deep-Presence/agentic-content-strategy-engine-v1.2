'use client';

interface GaugeProps {
  score: number;
  max?: number;
  color: string;
  label: string;
  grade: string;
  gradeColor: string;
  description: string;
}

function ScoreGauge({ score, max = 100, color, label, grade, gradeColor, description }: GaugeProps) {
  const pct = score / max;
  const r = 70;
  const circumference = Math.PI * r;
  const offset = circumference * (1 - pct);

  return (
    <div className="text-center">
      <svg viewBox="0 0 160 95" width={240} height={140}>
        {/* Background arc */}
        <path d="M 10 85 A 70 70 0 0 1 150 85" fill="none" stroke="var(--border)" strokeWidth="14" strokeLinecap="round" />
        {/* Fill arc */}
        <path d="M 10 85 A 70 70 0 0 1 150 85" fill="none" stroke={color} strokeWidth="14" strokeLinecap="round"
          strokeDasharray={`${circumference}`} strokeDashoffset={`${offset}`}
          style={{ transition: 'stroke-dashoffset 1.2s ease-out' }} />
        {/* Score text */}
        <text x="80" y="72" textAnchor="middle" style={{ fontFamily: 'var(--font-mono)', fontSize: '40px', fontWeight: 700, fill: 'var(--text-primary)' }}>
          {score}
        </text>
      </svg>
      <div style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-primary)' }}>{label}</div>
      <span style={{
        fontSize: '12px', fontWeight: 600, padding: '2px 8px', borderRadius: '4px',
        background: gradeColor, color: 'white', display: 'inline-block', marginTop: '4px'
      }}>
        {grade}
      </span>
      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '8px', maxWidth: '200px', margin: '8px auto 0' }}>
        {description}
      </div>
    </div>
  );
}

export function GapGauge() {
  return (
    <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: '6px', padding: '16px' }}>
      <div className="flex items-start justify-center gap-12 flex-wrap">
        <ScoreGauge
          score={95}
          color="#34B27B"
          label="Site Health"
          grade="Grade A"
          gradeColor="#34B27B"
          description="Your site is technically excellent."
        />
        <ScoreGauge
          score={38.7}
          color="#E5484D"
          label="AEO Readiness"
          grade="Grade F"
          gradeColor="#E5484D"
          description="Your content isn't structured for AI citation."
        />
      </div>
      {/* Gap narrative */}
      <div style={{
        maxWidth: '400px', margin: '16px auto 0', padding: '16px',
        border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: '6px',
        fontSize: '12px', color: 'var(--text-secondary)', textAlign: 'center', lineHeight: 1.6,
      }}>
        Your site is healthy, but AI engines can&apos;t extract useful answers from it.
        Focus: question headings, FAQ sections, comparison tables, and llms.txt.
      </div>
    </div>
  );
}
