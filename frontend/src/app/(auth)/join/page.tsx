'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Input, Badge } from '@/components/ui';
import Link from 'next/link';

export default function JoinPage() {
  const router = useRouter();
  const [step, setStep] = useState<'code' | 'details'>('code');
  const [inviteCode, setInviteCode] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [form, setForm] = useState({ fullName: '', email: '', password: '' });

  const update = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleVerify = (e: React.FormEvent) => {
    e.preventDefault();
    setCompanyName('Lovable');
    setStep('details');
  };

  const handleJoin = (e: React.FormEvent) => {
    e.preventDefault();
    router.push('/');
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
              <span className="text-[13px] text-text-primary font-medium">Joining:</span>
              <Badge variant="info">{companyName}</Badge>
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
              placeholder="jane@lovable.dev"
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
          <Button variant="primary" className="w-full mt-4 h-[36px] text-[14px]" type="submit">
            Join Team
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
