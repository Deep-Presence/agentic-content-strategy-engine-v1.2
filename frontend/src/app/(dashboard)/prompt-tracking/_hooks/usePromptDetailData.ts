'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/lib/api-client';
import { fetchPromptAnalytics, fetchPromptFanouts, fetchPromptAnswers } from '../_lib/api';
import {
  toCompetitorMention,
  toPlatformMentionRate,
  toQueryFanout,
  toAnswerHistoryRow,
} from '../_lib/adapters';
import type {
  CompetitorMention,
  PlatformMentionRate,
  QueryFanout,
  AnswerHistoryRow,
} from '../_lib/types';

export interface PromptDetailData {
  /** Competitor leaderboard */
  competitors: CompetitorMention[];
  /** Per-platform mention rates */
  platformRates: PlatformMentionRate[];
  /** Query fanout list */
  fanouts: QueryFanout[];
  /** Answer history rows */
  answerHistory: AnswerHistoryRow[];
  /** Per-section loading states */
  analyticsLoading: boolean;
  fanoutsLoading: boolean;
  answersLoading: boolean;
  /** Per-section errors */
  analyticsError: string | null;
  fanoutsError: string | null;
  answersError: string | null;
}

interface DateRangeParams {
  start_date?: string;
  end_date?: string;
  days?: number;
}

const EMPTY: PromptDetailData = {
  competitors: [],
  platformRates: [],
  fanouts: [],
  answerHistory: [],
  analyticsLoading: false,
  fanoutsLoading: false,
  answersLoading: false,
  analyticsError: null,
  fanoutsError: null,
  answersError: null,
};

export function usePromptDetailData(
  promptId: string | null,
  dateParams: DateRangeParams,
): PromptDetailData {
  const { companyName, companyDomain } = useAuth();
  const [competitors, setCompetitors] = useState<CompetitorMention[]>([]);
  const [platformRates, setPlatformRates] = useState<PlatformMentionRate[]>([]);
  const [fanouts, setFanouts] = useState<QueryFanout[]>([]);
  const [answerHistory, setAnswerHistory] = useState<AnswerHistoryRow[]>([]);

  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [fanoutsLoading, setFanoutsLoading] = useState(false);
  const [answersLoading, setAnswersLoading] = useState(false);

  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  const [fanoutsError, setFanoutsError] = useState<string | null>(null);
  const [answersError, setAnswersError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  const loadData = useCallback(
    async (pid: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const signal = controller.signal;

      const brandName = companyName || '';
      const brandDomain = companyDomain || '';

      // Reset state
      setAnalyticsLoading(true);
      setFanoutsLoading(true);
      setAnswersLoading(true);
      setAnalyticsError(null);
      setFanoutsError(null);
      setAnswersError(null);

      // Fire 3 requests in parallel — each section resolves independently
      const [analyticsResult, fanoutsResult, answersResult] = await Promise.allSettled([
        fetchPromptAnalytics(pid, dateParams, signal),
        fetchPromptFanouts(pid, signal),
        fetchPromptAnswers(pid, dateParams, signal),
      ]);

      if (signal.aborted) return;

      // Analytics
      if (analyticsResult.status === 'fulfilled') {
        const resp = analyticsResult.value;
        setCompetitors(resp.competitors.map((c) => toCompetitorMention(c, brandName, brandDomain)));
        setPlatformRates(resp.platforms.map(toPlatformMentionRate));
      } else {
        const err = analyticsResult.reason;
        setAnalyticsError(err instanceof ApiError ? err.detail : 'Failed to load analytics');
      }
      setAnalyticsLoading(false);

      // Fanouts
      if (fanoutsResult.status === 'fulfilled') {
        setFanouts(fanoutsResult.value.fanouts.map(toQueryFanout));
      } else {
        const err = fanoutsResult.reason;
        setFanoutsError(err instanceof ApiError ? err.detail : 'Failed to load fanouts');
      }
      setFanoutsLoading(false);

      // Answers
      if (answersResult.status === 'fulfilled') {
        setAnswerHistory(
          answersResult.value.responses.map((r) => toAnswerHistoryRow(r, brandName, brandDomain)),
        );
      } else {
        const err = answersResult.reason;
        setAnswersError(err instanceof ApiError ? err.detail : 'Failed to load answers');
      }
      setAnswersLoading(false);
    },
    [companyName, companyDomain, dateParams.start_date, dateParams.end_date, dateParams.days],
  );

  useEffect(() => {
    if (!promptId) {
      // Drawer closed — reset
      setCompetitors([]);
      setPlatformRates([]);
      setFanouts([]);
      setAnswerHistory([]);
      setAnalyticsError(null);
      setFanoutsError(null);
      setAnswersError(null);
      return;
    }
    loadData(promptId);
    return () => {
      abortRef.current?.abort();
    };
  }, [promptId, loadData]);

  if (!promptId) return EMPTY;

  return {
    competitors,
    platformRates,
    fanouts,
    answerHistory,
    analyticsLoading,
    fanoutsLoading,
    answersLoading,
    analyticsError,
    fanoutsError,
    answersError,
  };
}
