/**
 * API service layer for Brand Hub / Artifacts.
 * All calls go through BFF proxy via same-origin fetch.
 */

import { api, ApiError } from '@/lib/api-client';
import type {
  VoiceGuideResponse,
  PersonaListResponseAPI,
  KBHealthResponseAPI,
  KBDocType,
  ArtifactFileListResponse,
} from './types';

// ── Generic artifact file listing ────────────────────────

export function fetchArtifactFileList(
  artifactType: string,
  slug: string,
  signal?: AbortSignal,
): Promise<ArtifactFileListResponse> {
  return api.get<ArtifactFileListResponse>(
    `/api/v1/artifacts/${artifactType}/${slug}`,
    undefined,
    signal,
  );
}

// ── Knowledge Base ──────────────────────────────────────

export function fetchKBDocContent(
  slug: string,
  docType: KBDocType,
  version: number | string,
  signal?: AbortSignal,
): Promise<string> {
  return api.getText(
    `/api/v1/artifacts/knowledge_base/${slug}/${docType}/v${version}.md`,
    undefined,
    signal,
  );
}

export function fetchKBHealth(
  slug: string,
  signal?: AbortSignal,
): Promise<KBHealthResponseAPI> {
  return api.get<KBHealthResponseAPI>(
    `/api/v1/knowledge-base/${slug}/health`,
    undefined,
    signal,
  );
}

// ── Voice Style Guide ───────────────────────────────────

export function fetchVoiceGuide(
  slug: string,
  signal?: AbortSignal,
): Promise<VoiceGuideResponse> {
  return api.get<VoiceGuideResponse>(
    `/api/v1/voice-style-guide/${slug}/guide`,
    undefined,
    signal,
  );
}

// ── Audience Personas ───────────────────────────────────

export function fetchPersonaList(
  slug: string,
  signal?: AbortSignal,
): Promise<PersonaListResponseAPI> {
  return api.get<PersonaListResponseAPI>(
    `/api/v1/audience-persona/${slug}/personas`,
    undefined,
    signal,
  );
}

export function fetchPersonaContent(
  slug: string,
  personaId: string,
  version: number,
  signal?: AbortSignal,
): Promise<string> {
  return api.getText(
    `/api/v1/artifacts/audience_personas/${slug}/${personaId}/v${version}.md`,
    undefined,
    signal,
  );
}

// ── Pipeline Regeneration (auto-approved) ──────────────

export interface PipelineStartResponse {
  run_id: string;
  pipeline: string;
  company_slug: string;
  status: string;
  created_at: string;
}

export function regenerateKnowledgeBase(
  companyName: string,
  domain: string,
): Promise<PipelineStartResponse> {
  return api.post<PipelineStartResponse>(
    '/api/v1/knowledge-base/start',
    {
      company_name: companyName,
      domain,
      mode: 'full',
      force_rerun: true,
      auto_approve_checkpoints: [1, 2, 3],
    },
  );
}

export function regenerateAudiencePersonas(
  companyName: string,
  domain: string,
): Promise<PipelineStartResponse> {
  return api.post<PipelineStartResponse>(
    '/api/v1/audience-persona/start',
    {
      company_name: companyName,
      domain,
      force_rerun: true,
      auto_approve_checkpoints: [1, 2],
    },
  );
}

export function regenerateResearchOrchestrator(
  companyName: string,
  domain: string,
): Promise<PipelineStartResponse> {
  return api.post<PipelineStartResponse>(
    '/api/v1/research/start',
    {
      company_name: companyName,
      domain,
      force_rerun: true,
      auto_approve: {
        kb: [1, 2, 3],
        ap: [1, 2],
        vsg: [1],
      },
      pipelines: ['kb', 'ap', 'vsg'],
    },
  );
}

export function regenerateVoiceStyleGuide(
  companyName: string,
  domain: string,
): Promise<PipelineStartResponse> {
  return api.post<PipelineStartResponse>(
    '/api/v1/voice-style-guide/start',
    {
      company_name: companyName,
      domain,
      force_rerun: true,
      auto_approve_checkpoints: [1],
    },
  );
}

// ── Upload ──────────────────────────────────────────────

export interface UploadArtifactResponse {
  artifact_type: string;
  slug: string;
  filename: string;
  original_filename: string;
  size_bytes: number;
  storage_key: string;
}

export async function uploadArtifact(
  artifactType: string,
  slug: string,
  file: File,
  subPath?: string,
): Promise<UploadArtifactResponse> {
  const formData = new FormData();
  formData.append('file', file);

  let url = `/api/v1/artifacts/${artifactType}/${slug}/upload`;
  if (subPath) {
    url += `?sub_path=${encodeURIComponent(subPath)}`;
  }

  const res = await fetch(url, {
    method: 'POST',
    body: formData,
    credentials: 'same-origin',
  });

  if (!res.ok) {
    let detail = 'Upload failed';
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch { /* non-JSON */ }
    throw new ApiError(res.status, detail);
  }

  return res.json();
}
