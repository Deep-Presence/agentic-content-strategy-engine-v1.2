/**
 * Settings data-fetching hooks.
 * Mutation hooks invalidate relevant SWR caches after successful writes.
 */

import { useState, useCallback, useRef } from 'react';
import { useSWRConfig } from 'swr';
import { useApiQuery } from './useApiQuery';
import { apiPut, apiPost, ApiError } from '@/lib/api/client';
import { SETTINGS, AUTH } from '@/lib/api/endpoints';
import type { TeamListResponse, CompanyProfileSettingsResponse, PipelineDefaultsResponse } from '@/lib/api/types';

export function useTeam(slug: string | undefined) {
  return useApiQuery<TeamListResponse>(slug ? SETTINGS.team(slug) : null);
}

export function useProfile(slug: string | undefined) {
  return useApiQuery<CompanyProfileSettingsResponse>(slug ? SETTINGS.profile(slug) : null);
}

export function usePipelineDefaults(slug: string | undefined) {
  return useApiQuery<PipelineDefaultsResponse>(slug ? SETTINGS.pipelineDefaults(slug) : null);
}

export function useUpdateTeamMember(slug: string | undefined) {
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const reqIdRef = useRef(0);
  const { mutate } = useSWRConfig();

  const update = useCallback(async (userId: string, data: { role?: string; is_active?: boolean }) => {
    if (!slug || isUpdating) return;
    const id = ++reqIdRef.current;
    setIsUpdating(true);
    setError(null);
    try {
      await apiPut(SETTINGS.teamMember(slug, userId), data);
      // Invalidate team list cache
      mutate(SETTINGS.team(slug));
    } catch (err) {
      if (id === reqIdRef.current) {
        setError(err instanceof ApiError ? err : new ApiError(0, String(err)));
      }
    } finally {
      if (id === reqIdRef.current) setIsUpdating(false);
    }
  }, [slug, isUpdating, mutate]);

  return { update, isUpdating, error };
}

export function useUpdateProfile(slug: string | undefined) {
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const reqIdRef = useRef(0);
  const { mutate } = useSWRConfig();

  const update = useCallback(async (data: { name?: string; domain?: string; industry?: string }): Promise<boolean> => {
    if (!slug || isUpdating) return false;
    const id = ++reqIdRef.current;
    setIsUpdating(true);
    setError(null);
    try {
      await apiPut(SETTINGS.profile(slug), data);
      // Invalidate profile cache
      mutate(SETTINGS.profile(slug));
      return true;
    } catch (err) {
      if (id === reqIdRef.current) {
        setError(err instanceof ApiError ? err : new ApiError(0, String(err)));
      }
      return false;
    } finally {
      if (id === reqIdRef.current) setIsUpdating(false);
    }
  }, [slug, isUpdating, mutate]);

  return { update, isUpdating, error };
}

export function useUpdatePipelineDefaults(slug: string | undefined) {
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const reqIdRef = useRef(0);
  const { mutate } = useSWRConfig();

  const update = useCallback(async (data: Record<string, unknown>): Promise<boolean> => {
    if (!slug || isUpdating) return false;
    const id = ++reqIdRef.current;
    setIsUpdating(true);
    setError(null);
    try {
      await apiPut(SETTINGS.pipelineDefaults(slug), data);
      // Invalidate pipeline defaults cache
      mutate(SETTINGS.pipelineDefaults(slug));
      return true;
    } catch (err) {
      if (id === reqIdRef.current) {
        setError(err instanceof ApiError ? err : new ApiError(0, String(err)));
      }
      return false;
    } finally {
      if (id === reqIdRef.current) setIsUpdating(false);
    }
  }, [slug, isUpdating, mutate]);

  return { update, isUpdating, error };
}

export function useInvite() {
  const [isInviting, setIsInviting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const reqIdRef = useRef(0);

  const invite = useCallback(async (role: 'member' | 'viewer') => {
    if (isInviting) return null;
    const id = ++reqIdRef.current;
    setIsInviting(true);
    setError(null);
    try {
      const result = await apiPost<{ invite_code: string }>(AUTH.invite, { role });
      return result;
    } catch (err) {
      if (id === reqIdRef.current) {
        setError(err instanceof ApiError ? err : new ApiError(0, String(err)));
      }
      return null;
    } finally {
      if (id === reqIdRef.current) setIsInviting(false);
    }
  }, [isInviting]);

  return { invite, isInviting, error };
}
