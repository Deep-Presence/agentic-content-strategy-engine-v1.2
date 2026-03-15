'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Input } from '@/components/ui';
import Link from 'next/link';

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    companyName: '',
    domain: '',
    fullName: '',
    email: '',
    password: '',
  });

  const update = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    router.push('/onboarding');
  };

  return (
    <div className="max-w-[380px]">
      <h1 className="font-display text-[28px] font-semibold tracking-[-0.02em] text-text-primary mb-2">
        Create account
      </h1>
      <p className="text-[14px] text-text-secondary mb-8 leading-[1.6]">
        Set up your workspace to start tracking AI citations.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-[13px] font-medium text-text-secondary mb-1.5">
            Company Name
          </label>
          <Input
            type="text"
            placeholder="Acme Inc."
            value={form.companyName}
            onChange={update('companyName')}
            className="w-full h-[36px] text-[14px] px-3"
            required
          />
        </div>
        <div>
          <label className="block text-[13px] font-medium text-text-secondary mb-1.5">
            Website Domain
          </label>
          <Input
            type="text"
            placeholder="acme.com"
            value={form.domain}
            onChange={update('domain')}
            className="w-full h-[36px] text-[14px] px-3"
            required
          />
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
            placeholder="jane@acme.com"
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
          Create Account
        </Button>
      </form>
      <div className="mt-6 text-[13px] text-center">
        <span className="text-text-secondary">Already have an account? </span>
        <Link href="/login" className="text-accent hover:text-accent-hover transition-colors">
          Sign in
        </Link>
      </div>
    </div>
  );
}
