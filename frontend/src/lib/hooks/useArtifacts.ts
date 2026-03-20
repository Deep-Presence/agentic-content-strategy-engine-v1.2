/**
 * Artifacts data-fetching hooks backed by SWR.
 * Uses immutable caching since artifacts rarely change.
 */

import { useApiQuery } from './useApiQuery';
import { BRAND_DATA, ARTIFACTS } from '@/lib/api/endpoints';

interface ResearchArtifacts {
  company_context: { content: string | null; status: string; updated_at: string | null };
  personas: {
    id: string;
    name: string;
    type: string;
    content: string;
    status: string;
    updated_at: string | null;
  }[];
  style_guide: { content: string | null; status: string; updated_at: string | null };
}

interface ArtifactFile {
  name: string;
  size: number;
}

export function useResearchArtifacts(slug: string | undefined) {
  return useApiQuery<ResearchArtifacts>(
    slug ? BRAND_DATA.researchArtifacts(slug) : null,
    { immutable: true },
  );
}

export function useKBFileList(slug: string | undefined) {
  return useApiQuery<{ files: ArtifactFile[] }>(
    slug ? ARTIFACTS.list('knowledge_base', slug) : null,
    { immutable: true },
  );
}
