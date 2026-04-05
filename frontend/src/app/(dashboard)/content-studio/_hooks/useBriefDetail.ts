'use client';

import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { fetchBriefDetail, fetchStageContent } from '../_lib/api';
import { adaptBriefContent, assembleArticleContent } from '../_lib/adapters';
import type { BriefContent, ArticleContent } from '../_components/types';

/**
 * On-demand hook: loads brief detail + best available stage content
 * when a card is selected in the FullPageView.
 *
 * Loading strategy:
 * 1. Fetch brief detail (metadata, eval_history, exemplars, CPS)
 * 2. Build BriefContent from detail
 * 3. If available_stages includes "final" (or "enriched"/"draft"),
 *    fetch stage content and build ArticleContent
 */
export function useBriefDetail(briefId: string | null) {
  const { companySlug } = useAuth();
  const [briefContent, setBriefContent] = useState<BriefContent | null>(null);
  const [articleContent, setArticleContent] = useState<ArticleContent | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!briefId || !companySlug) {
      setBriefContent(null);
      setArticleContent(null);
      setIsLoading(false);
      setError(null);
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setError(null);

    (async () => {
      try {
        // Step 1: Fetch brief detail
        const detail = await fetchBriefDetail(
          companySlug,
          briefId,
          undefined,
          controller.signal,
        );
        if (controller.signal.aborted) return;

        // Step 2: Build BriefContent
        setBriefContent(adaptBriefContent(detail));

        // Step 3: Find best available article stage
        const STAGE_PREFERENCE = ['final', 'enriched', 'formatted', 'draft'] as const;
        const bestStage = STAGE_PREFERENCE.find((s) =>
          detail.available_stages.includes(s),
        );

        if (bestStage) {
          try {
            const stageData = await fetchStageContent(
              companySlug,
              briefId,
              bestStage,
              undefined,
              controller.signal,
            );
            if (controller.signal.aborted) return;

            const markdown =
              typeof stageData.content === 'string'
                ? stageData.content
                : JSON.stringify(stageData.content, null, 2);

            setArticleContent(assembleArticleContent(detail, markdown));
          } catch {
            // Stage content not available — article stays null
            if (!controller.signal.aborted) {
              setArticleContent(null);
            }
          }
        } else {
          setArticleContent(null);
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        const message =
          err instanceof Error ? err.message : 'Failed to load brief detail';
        setError(message);
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    })();

    return () => {
      controller.abort();
    };
  }, [briefId, companySlug]);

  return { briefContent, articleContent, isLoading, error };
}
