'use client';

import { ProgressBar, Badge, Button } from '@/components/ui';
import { cn } from '@/lib/utils';
import { Check } from 'lucide-react';

interface UsageMeter {
  label: string;
  used: number;
  limit: number;
  unit: string;
}

const usageMeters: UsageMeter[] = [
  { label: 'API Calls', used: 8420, limit: 15000, unit: 'calls' },
  { label: 'Content Pieces', used: 34, limit: 50, unit: 'pieces' },
  { label: 'Team Members', used: 4, limit: 10, unit: 'members' },
];

interface PlanColumn {
  name: string;
  price: string;
  current: boolean;
  features: string[];
}

const plans: PlanColumn[] = [
  {
    name: 'Starter',
    price: '$99/mo',
    current: false,
    features: ['5,000 API calls', '15 content pieces', '3 team members', 'Basic analytics', 'Email support'],
  },
  {
    name: 'Growth',
    price: '$499/mo',
    current: true,
    features: ['15,000 API calls', '50 content pieces', '10 team members', 'Advanced analytics', 'Priority support', 'Attribution dashboard'],
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    current: false,
    features: ['Unlimited API calls', 'Unlimited content', 'Unlimited members', 'Custom integrations', 'Dedicated CSM', 'SLA guarantee', 'SSO & SAML'],
  },
];

export function BillingTab() {
  return (
    <div className="space-y-5">
      {/* Current Plan */}
      <div className="bg-surface border-2 border-accent rounded-md p-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-[16px] font-semibold text-text-primary mb-1">
              Current Plan
            </h3>
            <div className="flex items-center gap-2">
              <span className="font-display text-[24px] font-semibold tracking-[-0.02em] text-text-primary">Growth</span>
              <span className="text-[14px] text-text-secondary">$499/mo</span>
              <Badge variant="success">Active</Badge>
            </div>
            <p className="text-[13px] text-text-secondary mt-1">Billed monthly. Next renewal on Apr 15, 2026.</p>
          </div>
        </div>
      </div>

      {/* Usage Meters */}
      <div className="bg-surface border border-border rounded-md p-4">
        <h3 className="text-[16px] font-semibold text-text-primary mb-4">
          Usage This Period
        </h3>
        <div className="space-y-4">
          {usageMeters.map((meter) => {
            const pct = (meter.used / meter.limit) * 100;
            return (
              <div key={meter.label}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[13px] font-medium text-text-primary">{meter.label}</span>
                  <span className="text-[13px] text-text-secondary">
                    {meter.used.toLocaleString()} / {meter.limit.toLocaleString()} {meter.unit}
                    <span className="text-[11px] text-text-tertiary ml-1">({Math.round(pct)}%)</span>
                  </span>
                </div>
                <ProgressBar value={meter.used} max={meter.limit} />
              </div>
            );
          })}
        </div>
      </div>

      {/* Plan Comparison */}
      <div className="bg-surface border border-border rounded-md p-4">
        <h3 className="text-[16px] font-semibold text-text-primary mb-4">
          Plan Comparison
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={cn(
                'border rounded-md p-4 flex flex-col',
                plan.current
                  ? 'border-accent bg-accent-subtle'
                  : 'border-border hover:border-border-strong transition-[border-color] duration-150'
              )}
            >
              <div className="mb-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-[14px] font-medium text-text-primary">{plan.name}</span>
                  {plan.current && <Badge variant="info">Current</Badge>}
                </div>
                <span className="font-display text-[22px] font-semibold tracking-[-0.02em] text-text-primary">{plan.price}</span>
              </div>
              <ul className="space-y-2 flex-1">
                {plan.features.map((f) => (
                  <li key={f} className="text-[13px] text-text-secondary flex items-start gap-2">
                    <Check size={14} strokeWidth={2} className="text-accent mt-0.5 flex-shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
              <div className="mt-4">
                {plan.current ? (
                  <Button variant="secondary" className="w-full" disabled>
                    Current Plan
                  </Button>
                ) : (
                  <Button variant={plan.name === 'Enterprise' ? 'secondary' : 'primary'} className="w-full">
                    {plan.name === 'Enterprise' ? 'Contact Sales' : 'Upgrade'}
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
