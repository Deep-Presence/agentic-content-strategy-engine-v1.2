'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';

interface BrandLogoProps {
  /** Domain to fetch logo for (e.g. "openai.com", "perplexity.ai") */
  domain: string;
  /** Size in px (renders at 2x for retina) */
  size?: number;
  className?: string;
  /** Text to show when all sources fail (defaults to first 2 chars of domain) */
  fallbackText?: string;
}

export function BrandLogo({ domain, size = 20, className, fallbackText }: BrandLogoProps) {
  const [src, setSrc] = useState(
    `https://www.google.com/s2/favicons?domain=${domain}&sz=${size * 2}`,
  );
  const [failed, setFailed] = useState(false);

  if (failed) {
    // Last resort: text initials in a subtle circle
    const initials =
      fallbackText ??
      domain
        .replace(/^www\./, '')
        .split('.')[0]
        .slice(0, 2)
        .toUpperCase();

    return (
      <span
        className={cn(
          'inline-flex items-center justify-center shrink-0',
          'bg-accent-subtle text-accent rounded-sm',
          'text-[10px] font-semibold font-body leading-none select-none',
          className,
        )}
        style={{ width: size, height: size, fontSize: Math.max(8, size * 0.45) }}
        title={domain}
      >
        {initials}
      </span>
    );
  }

  return (
    <img
      src={src}
      alt={domain}
      width={size}
      height={size}
      className={cn('shrink-0 rounded-sm', className)}
      loading="lazy"
      onError={() => {
        // Fallback chain: Google → Clearbit → Logo.dev → text
        if (src.includes('google.com')) {
          setSrc(`https://logo.clearbit.com/${domain}`);
        } else if (src.includes('clearbit.com')) {
          setSrc(`https://img.logo.dev/${domain}?token=pk_placeholder&size=${size * 2}`);
        } else {
          setFailed(true);
        }
      }}
    />
  );
}
