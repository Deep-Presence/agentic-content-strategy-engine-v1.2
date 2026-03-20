'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Input, Badge } from '@/components/ui';
import Link from 'next/link';
import { useAuthStore } from '@/stores/auth';

export default function JoinPage() {
  const router = useRouter();
  const { join, checkOnboardingNeeded, isLoading, error, clearError } = useAuthStore();
  const [step, setStep] = useState<'code' | 'details'>('code');
  const [inviteCode, setInviteCode] = useState('');
  const [form, setForm] = useState({ fullName: '', email: '', password: '' });

  const update = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleVerify = (e: React.FormEvent) => {
    e.preventDefault();
    // Move to details step — the actual invite validation happens on join
    setStep('details');
  };

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    const nameParts = form.fullName.trim().split(/\s+/);
    const firstName = nameParts[0] || '';
    const lastName = nameParts.slice(1).join(' ') || '';
    try {
      await join({
        invite_code: inviteCode,
        first_name: firstName,
        last_name: lastName,
        email: form.email,
        password: form.password,
      });
      const needsOnboarding = await checkOnboardingNeeded();
      router.push(needsOnboarding ? '/onboarding' : '/');
    } catch {
      // error is set in the store
    }
  };

  return (
    <div className="max-w-[380px]">
      <h1 className="font-display text-[28px] font-semibold tracking-[-0.02em] text-text-primary mb-2">
        Join workspace
      </h1>
      <p className="text-[14px] text-text-secondary mb-8 leading-[1.6]">
        Enter your invite code to join an existing team.
      </p>

      {error && (
        <div className="bg-error/10 border border-error/30 text-error text-[13px] rounded-md px-3 py-2 mb-4">
          {error}
        </div>
      )}

      {step === 'code' && (
        <form onSubmit={handleVerify} className="space-y-4">
          <div>
            <label className="block text-[13px] font-medium text-text-secondary mb-1.5">
              Invite Code
            </label>
            <Input
              type="text"
              placeholder="XXXX-XXXX-XXXX"
              value={inviteCode}
              onChange={(e) => setInviteCode(e.target.value)}
              className="w-full h-[36px] text-[14px] px-3 font-mono tracking-wider"
              required
            />
          </div>
          <Button variant="primary" className="w-full mt-4 h-[36px] text-[14px]" type="submit">
            Verify Code
          </Button>
        </form>
      )}

      {step === 'details' && (
        <form onSubmit={handleJoin} className="space-y-4">
          <div className="bg-accent-subtle border border-accent rounded-md p-3 mb-1">
            <div className="flex items-center gap-2">
              <span className="text-[13px] text-text-primary font-medium">Invite code:</span>
              <Badge variant="info">{inviteCode}</Badge>
            </div>
          </div>
          <div>
            <label className="block text-[13px] font-medium text-text-secondary mb-1.5">
              Full Name
            </label>
            <Input
              type="text"
              placeholder="Jane Smith"
              value={form.fullName}
              onChange={update('fullName')}
              className="w-full h-[36px] text-[14px] px-3"
              required
            />
          </div>
          <div>
            <label className="block text-[13px] font-medium text-text-secondary mb-1.5">
              Email
            </label>
            <Input
              type="email"
              placeholder="jane@company.com"
              value={form.email}
              onChange={update('email')}
              className="w-full h-[36px] text-[14px] px-3"
              required
            />
          </div>
          <div>
            <label className="block text-[13px] font-medium text-text-secondary mb-1.5">
              Password
            </label>
            <Input
              type="password"
              placeholder="Min. 8 characters"
              value={form.password}
              onChange={update('password')}
              className="w-full h-[36px] text-[14px] px-3"
              required
              minLength={8}
            />
          </div>
          <Button
            variant="primary"
            className="w-full mt-4 h-[36px] text-[14px]"
            type="submit"
            disabled={isLoading}
          >
            {isLoading ? 'Joining...' : 'Join Team'}
          </Button>
        </form>
      )}

      <div className="mt-6 text-[13px] text-center">
        <span className="text-text-secondary">No invite code? </span>
        <Link href="/register" className="text-accent hover:text-accent-hover transition-colors">
          Create new workspace
        </Link>
      </div>
    </div>
  );
}
