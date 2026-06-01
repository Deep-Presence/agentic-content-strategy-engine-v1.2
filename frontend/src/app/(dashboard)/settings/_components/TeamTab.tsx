'use client';

import { useState, useCallback } from 'react';
import { Button, Badge, Toast, Skeleton } from '@/components/ui';
import { Copy, RefreshCw, AlertCircle } from 'lucide-react';
import { useTeamData } from '../_hooks/useTeamData';
import { ROLE_OPTIONS, INVITE_ROLE_OPTIONS, ROLE_DESCRIPTIONS } from '../_lib/role-map';
import type { FrontendRole } from '../_lib/types';

export function TeamTab() {
  const {
    members,
    isLoading,
    error,
    inviteCode,
    isGenerating,
    canManageTeam,
    currentUserId,
    updateRole,
    generateInvite,
    refetch,
  } = useTeamData();

  const [inviteRole, setInviteRole] = useState<'member' | 'viewer'>('member');
  const [toast, setToast] = useState({ open: false, message: '', variant: 'success' as 'success' | 'error' });
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const handleRoleChange = useCallback(async (userId: string, newRole: FrontendRole) => {
    setUpdatingId(userId);
    try {
      await updateRole(userId, newRole);
      setToast({ open: true, message: 'Role updated', variant: 'success' });
    } catch {
      setToast({ open: true, message: 'Failed to update role', variant: 'error' });
    } finally {
      setUpdatingId(null);
    }
  }, [updateRole]);

  const handleGenerateInvite = useCallback(async () => {
    await generateInvite(inviteRole);
  }, [generateInvite, inviteRole]);

  const handleCopyCode = useCallback(() => {
    if (!inviteCode) return;
    navigator.clipboard.writeText(inviteCode);
    setToast({ open: true, message: 'Copied to clipboard', variant: 'success' });
  }, [inviteCode]);

  // ── Error state ──────────────────────────────────────────

  if (error && !isLoading && members.length === 0) {
    return (
      <div className="bg-surface border border-border rounded-md p-6 text-center">
        <AlertCircle size={24} strokeWidth={1.5} className="mx-auto mb-2 text-text-tertiary" />
        <p className="text-[14px] text-text-secondary mb-3">{error}</p>
        <Button variant="secondary" size="sm" onClick={refetch}>
          <RefreshCw size={14} strokeWidth={1.5} className="mr-1.5" />
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Members Table */}
      <div className="bg-surface border border-border rounded-md p-4">
        <h3 className="text-[16px] font-semibold text-text-primary mb-3">
          Team Members
        </h3>
        <div className="w-full overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                <th className="text-[11px] font-medium tracking-[0.06em] uppercase text-text-tertiary text-left py-[8px] px-[10px] border-b border-border">Name</th>
                <th className="text-[11px] font-medium tracking-[0.06em] uppercase text-text-tertiary text-left py-[8px] px-[10px] border-b border-border">Email</th>
                <th className="text-[11px] font-medium tracking-[0.06em] uppercase text-text-tertiary text-left py-[8px] px-[10px] border-b border-border">Role</th>
                <th className="text-[11px] font-medium tracking-[0.06em] uppercase text-text-tertiary text-left py-[8px] px-[10px] border-b border-border">Status</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                // Skeleton rows
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i} className="h-[40px]">
                    <td className="py-[8px] px-[10px] border-b border-border-subtle"><Skeleton className="h-4 w-28" /></td>
                    <td className="py-[8px] px-[10px] border-b border-border-subtle"><Skeleton className="h-4 w-40" /></td>
                    <td className="py-[8px] px-[10px] border-b border-border-subtle"><Skeleton className="h-6 w-20" /></td>
                    <td className="py-[8px] px-[10px] border-b border-border-subtle"><Skeleton className="h-5 w-14" /></td>
                  </tr>
                ))
              ) : (
                members.map((m) => {
                  const isSelf = m.id === currentUserId;
                  const canEdit = canManageTeam && !isSelf;

                  return (
                    <tr key={m.id} className="hover:bg-accent-subtle transition-colors h-[40px]">
                      <td className="py-[8px] px-[10px] text-[13px] text-text-primary border-b border-border-subtle font-medium">
                        {m.name}
                        {isSelf && <span className="text-[11px] text-text-tertiary ml-1.5">(you)</span>}
                      </td>
                      <td className="py-[8px] px-[10px] text-[13px] text-text-secondary border-b border-border-subtle">{m.email}</td>
                      <td className="py-[8px] px-[10px] border-b border-border-subtle">
                        {canEdit ? (
                          <div className="group relative">
                            <select
                              value={m.role}
                              onChange={(e) => handleRoleChange(m.id, e.target.value as FrontendRole)}
                              disabled={updatingId === m.id}
                              className="h-[30px] px-2 rounded-sm border border-border bg-surface text-[13px] text-text-primary outline-none cursor-pointer hover:border-border-strong transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {ROLE_OPTIONS.map((r) => (
                                <option key={r.value} value={r.value}>{r.label}</option>
                              ))}
                            </select>
                            <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block z-10 bg-surface-raised border border-border rounded-md px-2 py-1 shadow-float whitespace-nowrap">
                              <span className="text-[11px] text-text-secondary">{ROLE_DESCRIPTIONS[m.role]}</span>
                            </div>
                          </div>
                        ) : (
                          <Badge variant="neutral">
                            {ROLE_OPTIONS.find((r) => r.value === m.role)?.label ?? m.role}
                          </Badge>
                        )}
                      </td>
                      <td className="py-[8px] px-[10px] border-b border-border-subtle">
                        <Badge variant={m.status === 'active' ? 'success' : 'warning'}>
                          {m.status === 'active' ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Invite Section — superuser only */}
      {canManageTeam && (
        <div className="bg-surface border border-border rounded-md p-4">
          <h3 className="text-[16px] font-semibold text-text-primary mb-3">
            Generate Invite Code
          </h3>
          <p className="text-[13px] text-text-secondary mb-3">
            Generate a one-time invite code to share with a new team member.
          </p>
          <div className="flex items-end gap-3 flex-wrap">
            <div>
              <label className="text-[13px] font-medium text-text-secondary block mb-1.5">Role</label>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as 'member' | 'viewer')}
                className="h-[34px] px-3 rounded-sm border border-border bg-surface text-[13px] text-text-primary outline-none cursor-pointer hover:border-border-strong transition-colors"
              >
                {INVITE_ROLE_OPTIONS.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
            <Button onClick={handleGenerateInvite} disabled={isGenerating}>
              {isGenerating ? 'Generating...' : 'Generate Code'}
            </Button>
          </div>

          {inviteCode && (
            <div className="mt-4">
              <div className="flex items-center gap-2">
                <code className="font-mono text-[14px] bg-surface border border-border rounded-sm px-3 py-1.5 select-all text-text-primary">
                  {inviteCode}
                </code>
                <button
                  onClick={handleCopyCode}
                  className="p-1.5 rounded-sm border border-border hover:border-border-strong text-text-tertiary hover:text-text-primary transition-colors cursor-pointer"
                >
                  <Copy size={14} strokeWidth={1.5} />
                </button>
              </div>
              <p className="text-[13px] text-text-secondary mt-2">
                Share this code — the recipient can use it at <code className="font-mono text-[12px]">/join</code> to join your workspace.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Inline error for non-fatal errors */}
      {error && members.length > 0 && (
        <div className="bg-surface border border-error/30 rounded-md px-4 py-2.5 flex items-center gap-2">
          <AlertCircle size={14} strokeWidth={1.5} className="text-error shrink-0" />
          <span className="text-[13px] text-error">{error}</span>
        </div>
      )}

      <Toast
        open={toast.open}
        onClose={() => setToast({ ...toast, open: false })}
        variant={toast.variant}
        message={toast.message}
      />
    </div>
  );
}
