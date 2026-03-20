/**
 * Site Audit data-fetching hook backed by SWR.
 * Uses dependent fetching: list audits → get latest detail.
 */

import useSWR from 'swr';
import type { ApiError } from '@/lib/api/client';
import { SITE_AUDIT } from '@/lib/api/endpoints';
import type { AuditDetailResponse, AuditSummaryResponse } from '@/lib/api/types';

export interface UseSiteAuditLatestResult {
  audit: AuditDetailResponse | null;
  isLoading: boolean;
  error: ApiError | null;
}

export function useSiteAuditLatest(slug: string | undefined): UseSiteAuditLatestResult {
  // Step 1: fetch the audit list
  const {
    data: auditList,
    error: listError,
  } = useSWR<AuditSummaryResponse[], ApiError>(
    slug ? SITE_AUDIT.audits(slug) : null,
  );

  // Step 2: derive latest audit ID, then fetch detail (dependent key)
  const latestId = auditList && auditList.length > 0 ? auditList[0].audit_id : undefined;

  const {
    data: audit,
    error: detailError,
  } = useSWR<AuditDetailResponse, ApiError>(
    slug && latestId ? SITE_AUDIT.audit(slug, latestId) : null,
  );

  // Loading: slug provided but still waiting for data
  // Not loading if: auditList loaded but empty (no detail to fetch), or audit loaded, or error
  const listLoaded = auditList !== undefined;
  const emptyList = listLoaded && auditList.length === 0;
  const isLoading = slug !== undefined && !emptyList && audit === undefined && !listError && !detailError;

  return {
    audit: audit ?? null,
    isLoading,
    error: listError ?? detailError ?? null,
  };
}
