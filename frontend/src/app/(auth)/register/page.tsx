'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Input } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/lib/api-client';
import { AlertCircle } from 'lucide-react';
import Link from 'next/link';

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();

  const [form, setForm] = useState({
    companyName: '',
    domain: '',
    firstName: '',
    lastName: '',
    email: '',
    password: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await register({
        first_name: form.firstName,
        last_name: form.lastName,
        email: form.email,
        password: form.password,
        company_name: form.companyName,
        company_domain: form.domain,
      });
      router.push('/onboarding');
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
            disabled={isSubmitting}
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
            disabled={isSubmitting}
          />
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
            placeholder="jane@acme.com"
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
          <div className="flex items-center gap-2 px-3 py-2 rounded-sm border border-error bg-error-subtle text-[13px] text-error">
            <AlertCircle size={14} strokeWidth={1.5} className="flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
        <Button variant="primary" className="w-full mt-4 h-[36px] text-[14px]" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Creating account...' : 'Create Account'}
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
