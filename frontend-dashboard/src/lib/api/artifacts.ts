import { api } from './client';
import type { CompaniesResponse, ArtifactFilesResponse } from '@/types/common';

export type ArtifactType = 'company_context' | 'personas' | 'style_guides' | 'gap_analysis' | 'content';

export const artifacts = {
  listCompanies(): Promise<CompaniesResponse> {
    return api.get('/api/v1/artifacts/companies');
  },

  listFiles(type: ArtifactType, slug: string): Promise<ArtifactFilesResponse> {
    return api.get(`/api/v1/artifacts/${type}/${slug}`);
  },

  getContent<T = unknown>(type: ArtifactType, slug: string, filename: string): Promise<T> {
    return api.get(`/api/v1/artifacts/${type}/${slug}/${filename}`);
  },
};
