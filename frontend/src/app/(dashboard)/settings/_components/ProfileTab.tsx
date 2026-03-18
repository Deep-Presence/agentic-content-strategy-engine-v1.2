'use client';

import { useState, useEffect } from 'react';
import { Button, Input, Skeleton, Toast } from '@/components/ui';
import { useAuthStore } from '@/stores/auth';
import { useProfile, useUpdateProfile } from '@/lib/hooks/useSettings';

export function ProfileTab() {
  const slug = useAuthStore((s) => s.company?.slug);
  const userRole = useAuthStore((s) => s.user?.role);
  const { data: profile, isLoading, refetch } = useProfile(slug);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { update, isUpdating, error } = useUpdateProfile(slug);

  const [name, setName] = useState('');
  const [domain, setDomain] = useState('');
  const [industry, setIndustry] = useState('');
  const [toast, setToast] = useState({ open: false, message: '' });

  useEffect(() => {
    if (profile) {
      setName(profile.name);
      setDomain(profile.domain);
      setIndustry(profile.industry ?? '');
    }
  }, [profile]);

  const isSuperuser = userRole === 'superuser';

  const handleSave = async () => {
    const ok = await update({ name, domain, industry: industry || undefined });
    if (ok) {
      setToast({ open: true, message: 'Profile updated!' });
      refetch();
    }
  };

  if (isLoading) {
    return <div className="space-y-3"><Skeleton className="h-10 w-full rounded-md" /><Skeleton className="h-40 w-full rounded-md" /></div>;
  }

  return (
    <div className="space-y-6 max-w-lg">
      <div>
        <h3 className="text-[13px] font-semibold text-text-primary mb-3">Company Profile</h3>
        <div className="space-y-3">
          <div>
            <label className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-1">Company Name</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} disabled={!isSuperuser} />
          </div>
          <div>
            <label className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-1">Domain</label>
            <Input value={domain} onChange={(e) => setDomain(e.target.value)} disabled={!isSuperuser} />
          </div>
          <div>
            <label className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-1">Industry</label>
            <Input value={industry} onChange={(e) => setIndustry(e.target.value)} disabled={!isSuperuser} placeholder="e.g., B2B SaaS, Fintech" />
          </div>
          <div className="text-[10px] text-text-tertiary">
            Slug: <code className="font-mono text-text-secondary">{profile?.slug}</code>
          </div>
        </div>
      </div>

      {isSuperuser && (
        <Button variant="primary" size="sm" onClick={handleSave} disabled={isUpdating}>
          {isUpdating ? 'Saving...' : 'Save Changes'}
        </Button>
      )}

      {!isSuperuser && (
        <p className="text-[11px] text-text-tertiary">Only admins can edit the company profile.</p>
      )}

      <Toast open={toast.open} onClose={() => setToast({ ...toast, open: false })} variant="success" message={toast.message} />
    </div>
  );
}
