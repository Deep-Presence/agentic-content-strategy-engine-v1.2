'use client';

import { LocusLogo } from '@/components/ui';

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen">
      {/* Left: Form */}
      <div className="w-full md:w-1/2 bg-bg flex flex-col justify-center px-8 md:px-16">
        <div className="mb-12">
          <LocusLogo variant="compact" />
        </div>
        {children}
      </div>
      {/* Right: Brand Visual */}
      <div
        className="hidden md:flex w-1/2 relative items-center justify-center flex-col"
        style={{
          background: '#171717',
        }}
      >
        {/* Gradient mesh overlay */}
        <div
          className="absolute inset-0"
          style={{
            background: `radial-gradient(ellipse 60% 50% at 30% 40%, rgba(91,164,196,0.35) 0%, transparent 70%),
                         radial-gradient(ellipse 50% 60% at 70% 60%, rgba(6,182,212,0.25) 0%, transparent 70%),
                         radial-gradient(ellipse 40% 40% at 50% 50%, rgba(96,165,250,0.15) 0%, transparent 60%)`,
          }}
        />
        {/* Centered logo + tagline */}
        <div className="relative z-10 flex flex-col items-center gap-5">
          <LocusLogo variant="symbol" size={80} animated className="text-[#EDEDED]" />
          <p className="text-[16px]" style={{ color: '#A0A0A0' }}>
            See where you stand.
          </p>
        </div>
      </div>
    </div>
  );
}
