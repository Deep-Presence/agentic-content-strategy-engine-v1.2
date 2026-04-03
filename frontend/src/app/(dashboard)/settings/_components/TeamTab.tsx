'use client';

import { useState, useCallback } from 'react';
import { Button, Input, Badge, Toast } from '@/components/ui';
import { Copy } from 'lucide-react';

interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: 'admin' | 'editor' | 'viewer';
  status: 'active' | 'invited';
}

const initialMembers: TeamMember[] = [
  { id: '1', name: 'Sarah Chen', email: 'sarah@company.com', role: 'admin', status: 'active' },
  { id: '2', name: 'Marcus Rivera', email: 'marcus@company.com', role: 'editor', status: 'active' },
  { id: '3', name: 'Elena Kowalski', email: 'elena@company.com', role: 'editor', status: 'active' },
  { id: '4', name: 'Priya Sharma', email: 'priya@company.com', role: 'viewer', status: 'invited' },
];

const roles = ['admin', 'editor', 'viewer'] as const;

const roleDescriptions: Record<string, string> = {
  admin: 'Full access to all settings and data',
  editor: 'Can create and edit content, view analytics',
  viewer: 'Read-only access to dashboards',
};

export function TeamTab() {
  const [members, setMembers] = useState<TeamMember[]>(initialMembers);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'admin' | 'editor' | 'viewer'>('viewer');
  const [inviteCode] = useState('DP-INV-2024-A7X9');
  const [toast, setToast] = useState({ open: false, message: '' });

  const handleRoleChange = (id: string, role: 'admin' | 'editor' | 'viewer') => {
    setMembers(members.map((m) => (m.id === id ? { ...m, role } : m)));
  };

  const handleInvite = () => {
    if (!inviteEmail) return;
    setMembers([...members, {
      id: String(Date.now()),
      name: inviteEmail.split('@')[0],
      email: inviteEmail,
      role: inviteRole,
      status: 'invited',
    }]);
    setInviteEmail('');
    setToast({ open: true, message: `Invite sent to ${inviteEmail}` });
  };

  const handleCopyCode = useCallback(() => {
    navigator.clipboard.writeText(inviteCode);
    setToast({ open: true, message: 'Copied to clipboard' });
  }, [inviteCode]);

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
              {members.map((m) => (
                <tr key={m.id} className="hover:bg-accent-subtle transition-colors h-[40px]">
                  <td className="py-[8px] px-[10px] text-[13px] text-text-primary border-b border-border-subtle font-medium">{m.name}</td>
                  <td className="py-[8px] px-[10px] text-[13px] text-text-secondary border-b border-border-subtle">{m.email}</td>
                  <td className="py-[8px] px-[10px] border-b border-border-subtle">
                    <div className="group relative">
                      <select
                        value={m.role}
                        onChange={(e) => handleRoleChange(m.id, e.target.value as 'admin' | 'editor' | 'viewer')}
                        className="h-[30px] px-2 rounded-sm border border-border bg-surface text-[13px] text-text-primary outline-none cursor-pointer hover:border-border-strong transition-colors"
                      >
                        {roles.map((r) => (
                          <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
                        ))}
                      </select>
                      {/* Role description tooltip */}
                      <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block z-10 bg-surface-raised border border-border rounded-md px-2 py-1 shadow-float whitespace-nowrap">
                        <span className="text-[11px] text-text-secondary">{roleDescriptions[m.role]}</span>
                      </div>
                    </div>
                  </td>
                  <td className="py-[8px] px-[10px] border-b border-border-subtle">
                    <Badge variant={m.status === 'active' ? 'success' : 'warning'}>
                      {m.status === 'active' ? 'Active' : 'Invited'}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Invite Form */}
      <div className="bg-surface border border-border rounded-md p-4">
        <h3 className="text-[16px] font-semibold text-text-primary mb-3">
          Invite Team Member
        </h3>
        <div className="flex items-end gap-3 flex-wrap">
          <div className="flex-1 min-w-[220px]">
            <label className="text-[13px] font-medium text-text-secondary block mb-1.5">Email</label>
            <Input
              type="email"
              placeholder="colleague@company.com"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              className="text-[14px] h-[34px]"
            />
          </div>
          <div>
            <label className="text-[13px] font-medium text-text-secondary block mb-1.5">Role</label>
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as 'admin' | 'editor' | 'viewer')}
              className="h-[34px] px-3 rounded-sm border border-border bg-surface text-[13px] text-text-primary outline-none cursor-pointer hover:border-border-strong transition-colors"
            >
              {roles.map((r) => (
                <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
              ))}
            </select>
          </div>
          <Button onClick={handleInvite}>Send Invite</Button>
        </div>
      </div>

      {/* Invite Code */}
      <div className="bg-surface border border-border rounded-md p-4">
        <h3 className="text-[16px] font-semibold text-text-primary mb-3">
          Invite Code
        </h3>
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
        <p className="text-[13px] text-text-secondary mt-2">Share this code to let new members join your workspace.</p>
      </div>

      <Toast open={toast.open} onClose={() => setToast({ ...toast, open: false })} variant="success" message={toast.message} />
    </div>
  );
}
