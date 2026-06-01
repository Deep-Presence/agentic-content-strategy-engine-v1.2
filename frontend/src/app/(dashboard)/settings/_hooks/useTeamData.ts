'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/lib/api-client';
import {
  fetchTeamMembers,
  updateTeamMember,
  generateWorkspaceInvite,
} from '../_lib/api';
import { workspaceRoleToDisplay, displayRoleToWorkspace } from '../_lib/role-map';
import type { TeamMemberDisplay, FrontendRole, WorkspaceRole } from '../_lib/types';

interface UseTeamDataReturn {
  members: TeamMemberDisplay[];
  total: number;
  isLoading: boolean;
  error: string | null;
  inviteCode: string | null;
  isGenerating: boolean;
  canManageTeam: boolean;
  currentUserId: string;
  updateRole: (userId: string, newRole: FrontendRole) => Promise<void>;
  deactivateMember: (userId: string) => Promise<void>;
  generateInvite: (role: 'member' | 'viewer') => Promise<void>;
  refetch: () => void;
}

function toDisplay(m: {
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: WorkspaceRole;
  status: string;
}): TeamMemberDisplay {
  return {
    id: m.user_id,
    name: `${m.first_name} ${m.last_name}`.trim() || m.email,
    email: m.email,
    role: workspaceRoleToDisplay(m.role),
    workspaceRole: m.role,
    status: m.status === 'active' ? 'active' : 'inactive',
  };
}

export function useTeamData(): UseTeamDataReturn {
  const {
    activeWorkspaceSlug,
    isInitialized,
    hasRole,
    userId,
  } = useAuth();

  const workspaceSlug = activeWorkspaceSlug;
  const canManageTeam = hasRole('superuser');

  const [members, setMembers] = useState<TeamMemberDisplay[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [inviteCode, setInviteCode] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const abortRef = useRef<AbortController | null>(null);

  const loadData = useCallback(async (slug: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setError(null);

    try {
      const res = await fetchTeamMembers(slug, controller.signal);
      if (controller.signal.aborted) return;
      setMembers(res.members.map(toDisplay));
      setTotal(res.total);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      const msg = err instanceof ApiError ? err.detail : 'Failed to load team members';
      setError(msg);
    } finally {
      if (!controller.signal.aborted) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isInitialized || !workspaceSlug) return;
    loadData(workspaceSlug);
    return () => { abortRef.current?.abort(); };
  }, [isInitialized, workspaceSlug, loadData]);

  const refetch = useCallback(() => {
    if (workspaceSlug) loadData(workspaceSlug);
  }, [workspaceSlug, loadData]);

  const updateRole = useCallback(async (targetUserId: string, newRole: FrontendRole) => {
    if (!workspaceSlug) return;
    try {
      await updateTeamMember(workspaceSlug, targetUserId, {
        role: displayRoleToWorkspace(newRole),
      });
      refetch();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to update role';
      setError(msg);
      throw err;
    }
  }, [workspaceSlug, refetch]);

  const deactivateMember = useCallback(async (targetUserId: string) => {
    if (!workspaceSlug) return;
    try {
      await updateTeamMember(workspaceSlug, targetUserId, { status: 'suspended' });
      refetch();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to deactivate member';
      setError(msg);
      throw err;
    }
  }, [workspaceSlug, refetch]);

  const generateInvite = useCallback(async (role: 'member' | 'viewer') => {
    if (!workspaceSlug) return;
    setIsGenerating(true);
    try {
      const res = await generateWorkspaceInvite(workspaceSlug, role);
      setInviteCode(res.invite_code);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to generate invite code';
      setError(msg);
    } finally {
      setIsGenerating(false);
    }
  }, [workspaceSlug]);

  return {
    members,
    total,
    isLoading,
    error,
    inviteCode,
    isGenerating,
    canManageTeam,
    currentUserId: userId,
    updateRole,
    deactivateMember,
    generateInvite,
    refetch,
  };
}
