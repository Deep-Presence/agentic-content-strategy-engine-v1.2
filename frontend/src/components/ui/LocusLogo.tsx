'use client';

import { cn } from '@/lib/utils';
import { useEffect, useRef, useState } from 'react';

interface LocusLogoProps {
  size?: number;
  animated?: boolean;
  variant?: 'full' | 'compact' | 'symbol';
  className?: string;
}

export function LocusLogo({ size, animated = false, variant = 'full', className }: LocusLogoProps) {
  const [isAnimated, setIsAnimated] = useState(false);
  const ref = useRef<SVGSVGElement>(null);

  const symbolSize = size ?? (variant === 'full' ? 40 : variant === 'compact' ? 24 : 24);

  useEffect(() => {
    if (animated) {
      setIsAnimated(true);
    }
  }, [animated]);

  return (
    <div
      className={cn(
        'inline-flex items-center',
        variant === 'full' && 'gap-[20px]',
        variant === 'compact' && 'gap-[10px]',
        className
      )}
    >
      <svg
        ref={ref}
        width={symbolSize}
        height={symbolSize}
        viewBox="0 0 48 48"
        fill="none"
        className="flex-shrink-0"
      >
        {/* Center dot */}
        <circle
          cx="24"
          cy="24"
          r="3.5"
          fill="currentColor"
          style={isAnimated ? {
            animation: 'locusDotsIn 0.5s cubic-bezier(0.16,1,0.3,1) forwards, locusPulse 3s ease-in-out 1.2s infinite',
            opacity: 0,
            transformOrigin: 'center',
          } : undefined}
        />
        {/* Arc 1 */}
        <path
          d="M 40.17,18.75 A 17,17 0 1 1 11.37,35.38"
          stroke="currentColor"
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
          style={isAnimated ? {
            strokeDasharray: 120,
            strokeDashoffset: 120,
            animation: 'locusArcDraw 0.8s cubic-bezier(0.16,1,0.3,1) 0.3s forwards',
          } : undefined}
        />
        {/* Arc 2 */}
        <path
          d="M 7.83,29.25 A 17,17 0 0 1 36.63,12.62"
          stroke="currentColor"
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
          style={isAnimated ? {
            strokeDasharray: 120,
            strokeDashoffset: 120,
            animation: 'locusArcDraw 0.8s cubic-bezier(0.16,1,0.3,1) 0.5s forwards',
          } : undefined}
        />
      </svg>

      {variant === 'full' && (
        <span
          className="font-display font-medium tracking-[-0.01em] lowercase text-text-primary"
          style={{ fontSize: '22px' }}
        >
          deep{'\u00A0\u00A0'}presence
        </span>
      )}

      {variant === 'compact' && (
        <span
          className="font-display font-medium tracking-[-0.01em] lowercase text-text-primary"
          style={{ fontSize: '15px' }}
        >
          deep presence
        </span>
      )}
    </div>
  );
}
