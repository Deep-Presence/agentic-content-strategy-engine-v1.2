'use client';

export function BrandLogo({ domain, size = 20, className }: { domain: string; size?: number; className?: string }) {
  return (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=${size * 2}`}
      alt={domain} width={size} height={size} className={className}
      style={{ borderRadius: 3, flexShrink: 0 }}
      onError={(e) => { const t = e.target as HTMLImageElement; if (!t.dataset.fallback) { t.dataset.fallback = '1'; t.src = `https://logo.clearbit.com/${domain}`; } }}
    />
  );
}
