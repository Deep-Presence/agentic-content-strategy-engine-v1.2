'use client';

import { useState, useCallback } from 'react';
import { Button, Badge, Toast, Skeleton } from '@/components/ui';
import { Copy } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useTeam, useUpdateTeamMember, useInvite } from '@/lib/hooks/useSettings';

const ROLE_MAP: Record<string, string> = { superuser: 'admin', member: 'editor', viewer: 'viewer' };
const ROLE_REVERSE: Record<string, string> = { admin: 'superuser', editor: 'member', viewer: 'viewer' };
const roles = ['admin', 'editor', 'viewer'] as const;

const roleDescriptions: Record<string, string> = {
  admin: 'Full access to all settings and data',
  editor: 'Can create and edit content, view analytics',
  viewer: 'Read-only access to dashboards',
};

export function TeamTab() {
  const slug = useAuthStore((s) => s.company?.slug);
  const userRole = useAuthStore((s) => s.user?.role);
  const { data: teamData, isLoading, refetch } = useTeam(slug);
  const { update: updateMember, isUpdating } = useUpdateTeamMember(slug);
  const { invite, isInviting } = useInvite();

  const [inviteRole, setInviteRole] = useState<'editor' | 'viewer'>('viewer');
  const [inviteCode, setInviteCode] = useState<string | null>(null);
  const [toast, setToast] = useState({ open: false, message: '' });

  const handleRoleChange = useCallback(async (userId: string, displayRole: string) => {
    const backendRole = ROLE_REVERSE[displayRole] ?? 'viewer';
    await updateMember(userId, { role: backendRole });
    refetch();
  }, [updateMember, refetch]);

  const handleInvite = useCallback(async () => {
    // Only member/viewer can be invited — never superuser
    const backendRole = inviteRole === 'editor' ? 'member' : 'viewer';
    const result = await invite(backendRole as 'member' | 'viewer');
    if (result) {
      setInviteCode(result.invite_code);
      setToast({ open: true, message: 'Invite code generated!' });
    }
  }, [invite, inviteRole]);

  const isSuperuser = userRole === 'superuser';

  if (isLoading) {
    return <div className="space-y-3"><Skeleton className="h-12 w-full rounded-md" /><Skeleton className="h-40 w-full rounded-md" /></div>;
  }

  const members = (teamData?.members ?? []).map((m) => ({
    id: m.id,
    name: `${m.first_name} ${m.last_name}`,
    email: m.email,
    role: (ROLE_MAP[m.role] ?? 'viewer') as 'admin' | 'editor' | 'viewer',
    status: m.is_active ? 'active' as const : 'invited' as const,
  }));

  return (
    <div className="space-y-6">
      {/* Invite Section */}
      {isSuperuser && (
        <div className="bg-surface border border-border rounded-md p-4 space-y-3">
          <h3 className="text-[13px] font-semibold text-text-primary">Invite Team Member</h3>
          <div className="flex gap-2 items-end">
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as 'editor' | 'viewer')}
              className="h-[30px] px-2 rounded-sm border border-border bg-surface text-[12px] text-text-primary outline-none"
            >
              <option value="editor">editor</option>
              <option value="viewer">viewer</option>
            </select>
            <Button variant="primary" size="sm" onClick={handleInvite} disabled={isInviting}>
              {isInviting ? 'Generating...' : 'Generate Invite Code'}
            </Button>
          </div>
          {inviteCode && (
            <div className="flex items-center gap-2 bg-bg border border-border rounded-sm p-2">
              <code className="text-[12px] font-mono text-accent flex-1">{inviteCode}</code>
              <button
                className="p-1 hover:bg-accent-subtle rounded-sm transition-colors cursor-pointer"
                onClick={() => {
                  navigator.clipboard.writeText(inviteCode);
                  setToast({ open: true, message: 'Copied!' });
                }}
              >
                <Copy size={12} strokeWidth={1.5} className="text-text-secondary" />
              </button>
            </div>
          )}
          <p className="text-[10px] text-text-tertiary">Share this code for them to join via /join</p>
        </div>
      )}

      {/* Members Table */}
      <div className="bg-surface border border-border rounded-md overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              {['Member', 'Email', 'Role', 'Status'].map((h) => (
                <th key={h} className="text-left p-[8px_12px] text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.id} className="border-b border-border-subtle hover:bg-accent-subtle transition-colors">
                <td className="p-[8px_12px] text-[12px] text-text-primary font-medium">{m.name}</td>
                <td className="p-[8px_12px] text-[12px] text-text-secondary">{m.email}</td>
                <td className="p-[8px_12px]">
                  {isSuperuser ? (
                    <select
                      value={m.role}
                      onChange={(e) => handleRoleChange(m.id, e.target.value)}
                      disabled={isUpdating}
                      className="h-[24px] px-1.5 rounded-sm border border-border bg-surface text-[10px] text-text-primary outline-none cursor-pointer"
                    >
                      {roles.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  ) : (
                    <Badge variant="neutral">{m.role}</Badge>
                  )}
                </td>
                <td className="p-[8px_12px]">
                  <Badge variant={m.status === 'active' ? 'success' : 'warning'}>{m.status}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Role descriptions */}
      <div className="space-y-1">
        {Object.entries(roleDescriptions).map(([role, desc]) => (
          <p key={role} className="text-[10px] text-text-tertiary">
            <span className="font-medium text-text-secondary">{role}</span>: {desc}
          </p>
        ))}
      </div>

      <Toast open={toast.open} onClose={() => setToast({ ...toast, open: false })} variant="success" message={toast.message} />
    </div>
  );
}
