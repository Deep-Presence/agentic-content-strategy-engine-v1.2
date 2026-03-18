'use client';

import { useState } from 'react';
import { Button, Input } from '@/components/ui';
import { useAuthStore } from '@/stores/auth';

const INDUSTRIES = [
  'SaaS / Software', 'Developer Tools', 'FinTech', 'HealthTech',
  'EdTech', 'E-Commerce', 'Marketing / AdTech', 'AI / ML', 'Other',
];

interface ScreenInputProps {
  onNext: (data: { companyName: string; websiteUrl: string; industry: string; audience: string }) => void;
}

export function ScreenInput({ onNext }: ScreenInputProps) {
  const company = useAuthStore((s) => s.company);
  const [companyName, setCompanyName] = useState(company?.name ?? '');
  const [websiteUrl, setWebsiteUrl] = useState(company?.domain ? `https://${company.domain}` : '');
  const [industry, setIndustry] = useState('');
  const [audience, setAudience] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onNext({ companyName, websiteUrl, industry, audience });
  };

  return (
    <div className="max-w-[480px] mx-auto">
      <h1 className="font-display text-[24px] font-semibold tracking-[-0.02em] text-text-primary mb-2">
        Let&apos;s analyze your brand
      </h1>
      <p className="text-[14px] text-text-secondary mb-8 leading-[1.6]">
        We&apos;ll crawl your site, audit your content, and benchmark you across AI platforms.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-[13px] font-medium text-text-secondary mb-1.5">
            Company Name
          </label>
          <Input
            type="text"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            className="w-full h-[36px] text-[14px] px-3"
            required
          />
        </div>
        <div>
          <label className="block text-[13px] font-medium text-text-secondary mb-1.5">
            Website URL
          </label>
          <Input
            type="url"
            placeholder="https://example.com"
            value={websiteUrl}
            onChange={(e) => setWebsiteUrl(e.target.value)}
            className="w-full h-[36px] text-[14px] px-3"
            required
          />
        </div>
        <div>
          <label className="block text-[13px] font-medium text-text-secondary mb-1.5">
            Industry
          </label>
          <select
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            required
            className="w-full h-[36px] px-3 rounded-sm border border-border bg-surface font-body text-[14px] text-text-primary outline-none transition-[border-color] duration-[120ms] ease-out hover:border-border-strong focus:border-accent focus:border-2 focus:bg-surface-raised focus:shadow-[0_0_0_3px_var(--accent-subtle)]"
          >
            <option value="" className="text-text-tertiary">Select industry...</option>
            {INDUSTRIES.map((ind) => (
              <option key={ind} value={ind}>{ind}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-[13px] font-medium text-text-secondary mb-1.5">
            Target Audience
          </label>
          <textarea
            placeholder="Describe your primary audience (e.g., 'SaaS founders and indie developers building web apps')"
            value={audience}
            onChange={(e) => setAudience(e.target.value)}
            required
            rows={3}
            className="w-full px-3 py-2.5 rounded-sm border border-border bg-surface font-body text-[14px] text-text-primary outline-none transition-[border-color] duration-[120ms] ease-out hover:border-border-strong focus:border-accent focus:border-2 focus:bg-surface-raised focus:shadow-[0_0_0_3px_var(--accent-subtle)] placeholder:text-text-tertiary resize-none leading-[1.6]"
          />
        </div>
        <Button variant="primary" className="w-full mt-2 h-[36px] text-[14px]" type="submit">
          Begin Analysis &rarr;
        </Button>
      </form>
    </div>
  );
}
