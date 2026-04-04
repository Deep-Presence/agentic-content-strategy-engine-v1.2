'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/lib/api-client';
import { fetchTeamMembers, updateTeamMember, generateInviteCode } from '../_lib/api';
import { backendRoleToDisplay, displayRoleToBackend } from '../_lib/role-map';
import type { TeamMemberDisplay, FrontendRole, BackendRole } from '../_lib/types';

interface UseTeamDataReturn {
  members: TeamMemberDisplay[];
  total: number;
  isLoading: boolean;
  error: string | null;
  inviteCode: string | null;
  isGenerating: boolean;
  isSuperuser: boolean;
  currentUserId: string;
  updateRole: (userId: string, newRole: FrontendRole) => Promise<void>;
  deactivateMember: (userId: string) => Promise<void>;
  generateInvite: (role: 'member' | 'viewer') => Promise<void>;
  refetch: () => void;
}

function toDisplay(m: { id: string; email: string; first_name: string; last_name: string; role: BackendRole; is_active: boolean; created_at: string }): TeamMemberDisplay {
  return {
    id: m.id,
    name: `${m.first_name} ${m.last_name}`.trim() || m.email,
    email: m.email,
    role: backendRoleToDisplay(m.role),
    backendRole: m.role,
    status: m.is_active ? 'active' : 'inactive',
    createdAt: m.created_at,
  };
}

export function useTeamData(): UseTeamDataReturn {
  const { companySlug, isInitialized, isSuperuser, userId } = useAuth();

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
    if (!isInitialized || !companySlug) return;
    loadData(companySlug);
    return () => { abortRef.current?.abort(); };
  }, [isInitialized, companySlug, loadData]);

  const refetch = useCallback(() => {
    if (companySlug) loadData(companySlug);
  }, [companySlug, loadData]);

  const updateRole = useCallback(async (targetUserId: string, newRole: FrontendRole) => {
    if (!companySlug) return;
    try {
      const backendRole = displayRoleToBackend(newRole);
      await updateTeamMember(companySlug, targetUserId, { role: backendRole });
      refetch();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to update role';
      setError(msg);
      throw err;
    }
  }, [companySlug, refetch]);

  const deactivateMember = useCallback(async (targetUserId: string) => {
    if (!companySlug) return;
    try {
      await updateTeamMember(companySlug, targetUserId, { is_active: false });
      refetch();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to deactivate member';
      setError(msg);
      throw err;
    }
  }, [companySlug, refetch]);

  const generateInvite = useCallback(async (role: 'member' | 'viewer') => {
    setIsGenerating(true);
    try {
      const res = await generateInviteCode(role);
      setInviteCode(res.invite_code);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to generate invite code';
      setError(msg);
    } finally {
      setIsGenerating(false);
    }
  }, []);

  return {
    members,
    total,
    isLoading,
    error,
    inviteCode,
    isGenerating,
    isSuperuser,
    currentUserId: userId,
    updateRole,
    deactivateMember,
    generateInvite,
    refetch,
  };
}
