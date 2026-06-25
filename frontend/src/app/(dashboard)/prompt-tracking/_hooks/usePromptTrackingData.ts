'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/lib/api-client';
import { fetchEnrichedPrompts } from '../_lib/api';
import { toPromptRow, deriveTopics } from '../_lib/adapters';
import type { PromptRow, Topic } from '../_lib/types';

export interface PromptTrackingData {
  prompts: PromptRow[];
  topics: Topic[];
  total: number;
  periodStart: string;
  periodEnd: string;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

interface DateRangeParams {
  start_date?: string;
  end_date?: string;
  days?: number;
}

export function usePromptTrackingData(
  dateParams: DateRangeParams,
  category?: string,
  search?: string,
): PromptTrackingData {
  const { companySlug, isInitialized } = useAuth();
  const [prompts, setPrompts] = useState<PromptRow[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [total, setTotal] = useState(0);
  const [periodStart, setPeriodStart] = useState('');
  const [periodEnd, setPeriodEnd] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const loadData = useCallback(
    async (slug: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const signal = controller.signal;

      setIsLoading(true);
      setError(null);

      try {
        const resp = await fetchEnrichedPrompts(
          {
            ...dateParams,
            category: category || undefined,
            search: search || undefined,
          },
          signal,
        );

        if (signal.aborted) return;

        const rows = resp.prompts.map(toPromptRow);
        setPrompts(rows);
        setTopics(deriveTopics(rows));
        setTotal(resp.total);
        setPeriodStart(resp.period_start);
        setPeriodEnd(resp.period_end);
      } catch (err) {
        if (signal.aborted) return;
        if (err instanceof ApiError) {
          setError(err.detail);
        } else {
          setError('Unable to load prompts. Please try again.');
        }
      } finally {
        if (!signal.aborted) {
          setIsLoading(false);
        }
      }
    },
    [dateParams.start_date, dateParams.end_date, dateParams.days, category, search],
  );

  useEffect(() => {
    if (!isInitialized || !companySlug) return;
    loadData(companySlug);
    return () => {
      abortRef.current?.abort();
    };
  }, [isInitialized, companySlug, loadData]);

  const refetch = useCallback(() => {
    if (companySlug) loadData(companySlug);
  }, [companySlug, loadData]);

  return {
    prompts,
    topics,
    total,
    periodStart,
    periodEnd,
    isLoading,
    error,
    refetch,
  };
}
