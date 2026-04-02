'use client';

import { useState, useCallback } from 'react';

interface BrandLogoProps {
  domain: string;
  size?: number;
  isCompany?: boolean;
  className?: string;
}

/**
 * Renders a brand logo with Clearbit → Google Favicon → Logo.dev → Text fallback chain.
 * Company logo gets teal ring with subtle glow.
 */
export function BrandLogo({ domain, size = 24, isCompany = false, className = '' }: BrandLogoProps) {
  const cleanDomain = domain.replace(/^(www\.)/, '');
  const [fallbackLevel, setFallbackLevel] = useState(0);

  const sources = [
    `https://logo.clearbit.com/${cleanDomain}`,
    `https://img.logo.dev/${cleanDomain}?token=pk_anonymous&size=64`,
    `https://www.google.com/s2/favicons?domain=${cleanDomain}&sz=64`,
  ];

  const handleError = useCallback(() => {
    setFallbackLevel(prev => prev + 1);
  }, []);

  const initials = cleanDomain
    .replace(/\.(com|io|dev|org|net|co|ai)$/, '')
    .slice(0, 2)
    .toUpperCase();

  const ringClasses = isCompany
    ? 'ring-[1.5px] ring-accent shadow-[0_0_6px_rgba(91,164,196,0.4)]'
    : '';

  if (fallbackLevel >= sources.length) {
    return (
      <div
        className={`inline-flex items-center justify-center rounded-full bg-surface-raised border border-border font-mono font-medium text-text-tertiary shrink-0 ${ringClasses} ${className}`}
        style={{ width: size, height: size, fontSize: Math.max(7, size * 0.35) }}
        title={cleanDomain}
      >
        {initials}
      </div>
    );
  }

  return (
    <div
      className={`inline-flex items-center justify-center rounded-full bg-surface-raised shrink-0 overflow-hidden ${ringClasses} ${className}`}
      style={{ width: size, height: size }}
      title={cleanDomain}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={sources[fallbackLevel]}
        alt={cleanDomain}
        width={size}
        height={size}
        onError={handleError}
        className="w-full h-full object-contain"
        crossOrigin="anonymous"
        referrerPolicy="no-referrer"
      />
    </div>
  );
}
