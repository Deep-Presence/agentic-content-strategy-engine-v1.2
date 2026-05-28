'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Input } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/lib/api-client';
import { AlertCircle, KeyRound } from 'lucide-react';
import Link from 'next/link';

export default function JoinPage() {
  const router = useRouter();
  const { join } = useAuth();

  const [step, setStep] = useState<'code' | 'details'>('code');
  const [inviteCode, setInviteCode] = useState('');
  const [form, setForm] = useState({ firstName: '', lastName: '', email: '', password: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleVerify = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!inviteCode.trim()) {
      setError('Please enter an invite code.');
      return;
    }
    setStep('details');
  };

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await join({
        invite_code: inviteCode.trim(),
        first_name: form.firstName,
        last_name: form.lastName,
        email: form.email,
        password: form.password,
      });
      router.push('/');
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Something went wrong. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetToStep1 = () => {
    setStep('code');
    setError(null);
    setInviteCode('');
  };

  return (
    <div className="max-w-[380px]">
      <h1 className="font-display text-[28px] font-semibold tracking-[-0.02em] text-text-primary mb-2">
        Join workspace
      </h1>
      <p className="text-[14px] text-text-secondary mb-8 leading-[1.6]">
        Enter your invite code to join an existing team.
      </p>

      {step === 'code' && (
        <form onSubmit={handleVerify} className="space-y-4">
          <div>
            <label className="block text-[13px] font-medium text-text-secondary mb-1.5">
              Invite Code
            </label>
            <Input
              type="text"
              placeholder="Enter your invite code"
              value={inviteCode}
              onChange={(e) => setInviteCode(e.target.value)}
              className="w-full h-[36px] text-[14px] px-3 font-mono tracking-wider"
              required
            />
          </div>
          {error && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-sm border border-error bg-error-subtle text-[13px] text-error">
              <AlertCircle size={14} strokeWidth={1.5} className="flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
          <Button variant="primary" className="w-full mt-4 h-[36px] text-[14px]" type="submit">
            Verify Code
          </Button>
        </form>
      )}

      {step === 'details' && (
        <form onSubmit={handleJoin} className="space-y-4">
          <div className="bg-accent-subtle border border-accent/30 rounded-sm p-3 mb-1">
            <div className="flex items-center gap-2">
              <KeyRound size={14} strokeWidth={1.5} className="text-accent flex-shrink-0" />
              <span className="text-[13px] text-text-primary">
                Using invite code: <span className="font-mono font-medium">{inviteCode}</span>
              </span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[13px] font-medium text-text-secondary mb-1.5">
                First Name
              </label>
              <Input
                type="text"
                placeholder="Jane"
                value={form.firstName}
                onChange={update('firstName')}
                className="w-full h-[36px] text-[14px] px-3"
                required
                disabled={isSubmitting}
              />
            </div>
            <div>
              <label className="block text-[13px] font-medium text-text-secondary mb-1.5">
                Last Name
              </label>
              <Input
                type="text"
                placeholder="Smith"
                value={form.lastName}
                onChange={update('lastName')}
                className="w-full h-[36px] text-[14px] px-3"
                required
                disabled={isSubmitting}
              />
            </div>
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
              disabled={isSubmitting}
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
              maxLength={128}
              disabled={isSubmitting}
            />
          </div>
          {error && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2 px-3 py-2 rounded-sm border border-error bg-error-subtle text-[13px] text-error">
                <AlertCircle size={14} strokeWidth={1.5} className="flex-shrink-0" />
                <span>{error}</span>
              </div>
              <button
                type="button"
                onClick={resetToStep1}
                className="text-[13px] text-accent hover:text-accent-hover transition-colors text-left"
              >
                Try a different code
              </button>
            </div>
          )}
          <Button variant="primary" className="w-full mt-4 h-[36px] text-[14px]" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Joining...' : 'Join Team'}
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
