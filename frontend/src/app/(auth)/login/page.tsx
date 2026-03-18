'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Input } from '@/components/ui';
import Link from 'next/link';
import { useAuthStore } from '@/stores/auth';

export default function LoginPage() {
  const router = useRouter();
  const { login, checkOnboardingNeeded, isLoading, error, clearError } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    try {
      await login(email, password);
      const needsOnboarding = await checkOnboardingNeeded();
      router.push(needsOnboarding ? '/onboarding' : '/');
    } catch {
      // error is set in the store
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
      {error && (
        <div className="bg-error/10 border border-error/30 text-error text-[13px] rounded-md px-3 py-2 mb-4">
          {error}
        </div>
      )}
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
          />
        </div>
        <Button
          variant="primary"
          className="w-full mt-4 h-[36px] text-[14px]"
          type="submit"
          disabled={isLoading}
        >
          {isLoading ? 'Signing in...' : 'Sign In'}
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
