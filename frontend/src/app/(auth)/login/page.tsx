'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button, Input } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/lib/api-client';
import { AlertCircle } from 'lucide-react';
import Link from 'next/link';

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login({ email, password });
      const redirect = searchParams.get('redirect') || '/';
      router.push(redirect);
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
        Sign in
      </h1>
      <p className="text-[14px] text-text-secondary mb-8 leading-[1.6]">
        Enter your credentials to access your workspace.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-[13px] font-medium text-text-secondary mb-1.5">
            Email
          </label>
          <Input
            type="email"
            placeholder="you@company.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
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
            placeholder="Enter password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full h-[36px] text-[14px] px-3"
            required
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
          {isSubmitting ? 'Signing in...' : 'Sign In'}
        </Button>
      </form>
      <div className="mt-6 flex items-center justify-between text-[13px]">
        <Link href="/register" className="text-accent hover:text-accent-hover transition-colors">
          Create account
        </Link>
        <Link href="/join" className="text-text-secondary hover:text-text-primary transition-colors">
          Join with invite code
        </Link>
      </div>
    </div>
  );
}
