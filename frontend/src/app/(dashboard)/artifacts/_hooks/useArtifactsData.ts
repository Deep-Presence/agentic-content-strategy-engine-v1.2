'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/lib/api-client';
import type { KBDocument, VoiceGuide } from '@/types';
import type { PersonaListItemAPI, KBHealthResponseAPI, ArtifactFileListResponse } from '../_lib/types';
import { KB_DOC_TYPES } from '../_lib/types';
import { fetchKBDocContent, fetchKBHealth, fetchVoiceGuide, fetchPersonaList, fetchArtifactFileList } from '../_lib/api';
import { parseVoiceGuideMarkdown } from '../_lib/parse-voice-guide';
import { buildKBDocument } from '../_lib/adapters';

export interface ArtifactsData {
  kbDocs: KBDocument[];
  voiceGuide: VoiceGuide | null;
  voiceGuideRaw: string;
  personas: PersonaListItemAPI[];
  kbHealth: KBHealthResponseAPI | null;
  kbFileList: ArtifactFileListResponse | null;
  vsgFileList: ArtifactFileListResponse | null;
  personaFileList: ArtifactFileListResponse | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useArtifactsData(): ArtifactsData {
  const { companySlug, isInitialized } = useAuth();
  const [kbDocs, setKbDocs] = useState<KBDocument[]>([]);
  const [voiceGuide, setVoiceGuide] = useState<VoiceGuide | null>(null);
  const [voiceGuideRaw, setVoiceGuideRaw] = useState('');
  const [personas, setPersonas] = useState<PersonaListItemAPI[]>([]);
  const [kbHealth, setKbHealth] = useState<KBHealthResponseAPI | null>(null);
  const [kbFileList, setKbFileList] = useState<ArtifactFileListResponse | null>(null);
  const [vsgFileList, setVsgFileList] = useState<ArtifactFileListResponse | null>(null);
  const [personaFileList, setPersonaFileList] = useState<ArtifactFileListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const loadData = useCallback(async (slug: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const signal = controller.signal;

    setIsLoading(true);
    setError(null);

    try {
      // Phase 1: Fetch health + voice guide + persona list + file lists in parallel
      const [healthResult, vsgResult, personaResult, kbFilesResult, vsgFilesResult, personaFilesResult] = await Promise.allSettled([
        fetchKBHealth(slug, signal),
        fetchVoiceGuide(slug, signal),
        fetchPersonaList(slug, signal),
        fetchArtifactFileList('knowledge_base', slug, signal),
        fetchArtifactFileList('voice_style_guide', slug, signal),
        fetchArtifactFileList('audience_personas', slug, signal),
      ]);

      if (signal.aborted) return;

      const health = healthResult.status === 'fulfilled' ? healthResult.value : null;
      const vsg = vsgResult.status === 'fulfilled' ? vsgResult.value : null;
      const personaList = personaResult.status === 'fulfilled' ? personaResult.value : null;

      setKbHealth(health);
      setPersonas(personaList?.personas ?? []);
      setKbFileList(kbFilesResult.status === 'fulfilled' ? kbFilesResult.value : null);
      setVsgFileList(vsgFilesResult.status === 'fulfilled' ? vsgFilesResult.value : null);
      setPersonaFileList(personaFilesResult.status === 'fulfilled' ? personaFilesResult.value : null);

      if (vsg) {
        setVoiceGuideRaw(vsg.guide_md);
        setVoiceGuide(parseVoiceGuideMarkdown(vsg.guide_md));
      } else {
        setVoiceGuideRaw('');
        setVoiceGuide(null);
      }

      // Phase 2: Fetch KB doc contents in parallel
      const kbFetches = KB_DOC_TYPES.map(async (docType) => {
        const version = health?.doc_health?.[docType]?.current_version ?? 1;
        try {
          const content = await fetchKBDocContent(slug, docType, version, signal);
          return buildKBDocument(docType, content, health);
        } catch (err) {
          if (err instanceof ApiError && err.status === 404) return null;
          throw err;
        }
      });

      const kbResults = await Promise.allSettled(kbFetches);
      if (signal.aborted) return;

      const docs = kbResults
        .filter((r): r is PromiseFulfilledResult<KBDocument | null> => r.status === 'fulfilled')
        .map((r) => r.value)
        .filter((doc): doc is KBDocument => doc !== null);

      setKbDocs(docs);

      const allFailed =
        healthResult.status === 'rejected' &&
        vsgResult.status === 'rejected' &&
        personaResult.status === 'rejected' &&
        docs.length === 0;

      if (allFailed) {
        const firstError = healthResult.status === 'rejected' ? healthResult.reason : null;
        if (firstError instanceof ApiError && firstError.status !== 404) {
          setError(firstError.detail);
        } else {
          setError('Unable to load artifacts. Please try again.');
        }
      }
    } catch (err) {
      if (signal.aborted) return;
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Unable to load artifacts. Please try again.');
      }
    } finally {
      if (!signal.aborted) {
        setIsLoading(false);
      }
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

  return {
    kbDocs, voiceGuide, voiceGuideRaw, personas, kbHealth,
    kbFileList, vsgFileList, personaFileList,
    isLoading, error, refetch,
  };
}
