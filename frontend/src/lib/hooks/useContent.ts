/**
 * Content data-fetching hooks.
 */

import { useApiQuery } from './useApiQuery';
import { CONTENT_DATA } from '@/lib/api/endpoints';
import type { ContentBriefListResponse, ContentBriefDetailResponse, StageContentResponse } from '@/lib/api/types';

export function useContentBriefs(slug: string | undefined) {
  return useApiQuery<ContentBriefListResponse>(
    slug ? CONTENT_DATA.briefs(slug) : null,
    { refreshInterval: 5000 },
  );
}

export function useContentBriefDetail(slug: string | undefined, briefId: string | null) {
  const path = slug && briefId ? CONTENT_DATA.brief(slug, briefId) : null;
  return useApiQuery<ContentBriefDetailResponse>(path);
}

export function useContentStage(slug: string | undefined, briefId: string | null, stage: string | null) {
  const path = slug && briefId && stage ? CONTENT_DATA.stage(slug, briefId, stage) : null;
  return useApiQuery<StageContentResponse>(path);
}
