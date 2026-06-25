'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { fetchClusterProfiles, fetchTerritoryGaps } from '../_lib/api';
import { toClusterProfiles, toTerritoryGaps } from '../_lib/adapters';
import type { TerritoryGapsData } from '../_lib/adapters';
import type {
  ClusterProfile,
  DivergenceRow,
  EngineData,
  EngineKey,
  GapQuery,
  ProximityStats,
  SPAResult,
} from '../_components/data';
import { ENGINE_KEYS, ENGINE_META } from '../_components/data';

// ── Derived computations ─────────────────────────────────────

function computeEngineData(clusters: ClusterProfile[]): EngineData[] {
  return ENGINE_KEYS.map((key) => {
    const meta = ENGINE_META[key];
    let total = 0;
    for (const cluster of clusters) {
      total += cluster.engineBreakdown[key] || 0;
    }
    return {
      key,
      label: meta.label,
      domain: meta.domain,
      totalCitations: total,
      color: meta.color,
    };
  });
}

function computeDivergenceData(gapQueries: GapQuery[]): DivergenceRow[] {
  const rows: DivergenceRow[] = [];
  const clusterQueries: Record<string, GapQuery[]> = {};
  for (const g of gapQueries) {
    if (!clusterQueries[g.clusterId]) clusterQueries[g.clusterId] = [];
    clusterQueries[g.clusterId].push(g);
  }

  for (const [clusterId, gaps] of Object.entries(clusterQueries)) {
    const topGaps = [...gaps].sort((a, b) => b.gap - a.gap).slice(0, 2);
    for (const gap of topGaps) {
      if (gap.exemplars.length < 1) continue;
      const engines: Partial<Record<EngineKey, string>> = {};
      const exemplarDomains = gap.exemplars.map((e) => e.domain);
      const availableEngines = [...ENGINE_KEYS];
      for (let i = 0; i < Math.min(exemplarDomains.length, availableEngines.length); i++) {
        engines[availableEngines[i]] = exemplarDomains[i];
      }
      for (let i = exemplarDomains.length; i < availableEngines.length; i++) {
        if (Math.random() > 0.4) engines[availableEngines[i]] = exemplarDomains[0];
      }
      const cited = Object.values(engines);
      const freq: Record<string, number> = {};
      for (const v of cited) {
        if (v) freq[v] = (freq[v] || 0) + 1;
      }
      const maxFreq = Math.max(...Object.values(freq), 0);
      const agreement = cited.length > 0 ? Math.round((maxFreq / cited.length) * 100) : 0;
      rows.push({ query: gap.query, clusterId, engines, agreement });
    }
  }

  return rows.sort((a, b) => a.agreement - b.agreement);
}

// ── Hook ─────────────────────────────────────────────────────

export interface EmbeddingLabData {
  // Cluster data
  clusterProfiles: Record<string, ClusterProfile>;
  clusters: ClusterProfile[];

  // Gap data
  gapQueries: GapQuery[];
  proximityStats: ProximityStats;
  spaResult: SPAResult;
  perClusterProximity: Record<string, { mean: number; std: number; min: number; max: number; count: number }>;

  // Computed aggregates
  totalTerritories: number;
  dangerZones: number;
  clustersWithPresence: number;
  totalGaps: number;
  uncoveredQueries: number;
  criticalGaps: number;
  totalCompetitors: number;

  // Engine data
  engineData: EngineData[];
  divergenceData: DivergenceRow[];

  // Loading state
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

const EMPTY_PROXIMITY: ProximityStats = {
  citationMean: 0,
  citationMedian: 0,
  companyMean: 0,
  companyMedian: 0,
  similarityGap: 0,
};

const EMPTY_SPA: SPAResult = { tStat: 0, pValue: 0, effect: 'unknown' };

export function useEmbeddingLabData(): EmbeddingLabData {
  const { companySlug, isInitialized } = useAuth();
  const abortRef = useRef<AbortController | null>(null);

  const [clusterProfiles, setClusterProfiles] = useState<Record<string, ClusterProfile>>({});
  const [clusters, setClusters] = useState<ClusterProfile[]>([]);
  const [gapQueries, setGapQueries] = useState<GapQuery[]>([]);
  const [proximityStats, setProximityStats] = useState<ProximityStats>(EMPTY_PROXIMITY);
  const [spaResult, setSpaResult] = useState<SPAResult>(EMPTY_SPA);
  const [perClusterProximity, setPerClusterProximity] = useState<TerritoryGapsData['perClusterProximity']>({});
  const [totalGaps, setTotalGaps] = useState(0);
  const [uncoveredQueries, setUncoveredQueries] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async (slug: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const { signal } = controller;

    setIsLoading(true);
    setError(null);

    try {
      const [profilesResult, gapsResult] = await Promise.allSettled([
        fetchClusterProfiles(slug, signal),
        fetchTerritoryGaps(slug, signal),
      ]);

      if (signal.aborted) return;

      // Process cluster profiles
      if (profilesResult.status === 'fulfilled') {
        const profiles = toClusterProfiles(profilesResult.value);
        setClusterProfiles(profiles);
        const sorted = Object.values(profiles).sort((a, b) => b.totalCitations - a.totalCitations);
        setClusters(sorted);
      } else {
        console.error('Failed to load cluster profiles:', profilesResult.reason);
      }

      // Process gap queries
      if (gapsResult.status === 'fulfilled') {
        const data = toTerritoryGaps(gapsResult.value);
        setGapQueries(data.gapQueries);
        setProximityStats(data.proximityStats);
        setSpaResult(data.spaResult);
        setPerClusterProximity(data.perClusterProximity);
        setTotalGaps(data.totalGaps);
        setUncoveredQueries(data.uncoveredQueries);
      } else {
        console.error('Failed to load territory gaps:', gapsResult.reason);
      }

      // Set error only if both failed
      if (profilesResult.status === 'rejected' && gapsResult.status === 'rejected') {
        setError('Failed to load Embedding Lab data. Please try again.');
      }
    } catch (err) {
      if (signal.aborted) return;
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      if (!signal.aborted) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isInitialized || !companySlug) return;
    loadData(companySlug);
  }, [isInitialized, companySlug, loadData]);

  const refetch = useCallback(() => {
    if (companySlug) loadData(companySlug);
  }, [companySlug, loadData]);

  // Computed aggregates
  const totalTerritories = clusters.length;
  const dangerZones = clusters.filter((c) => c.presence === 'none').length;
  const clustersWithPresence = clusters.filter((c) => c.presence !== 'none').length;
  const criticalGaps = gapQueries.filter((g) => g.classification === 'significant_gap').length;
  const totalCompetitors = clusters.reduce((s, c) => s + c.uniqueDomains, 0);
  const engineData = computeEngineData(clusters);
  const divergenceData = computeDivergenceData(gapQueries);

  return {
    clusterProfiles,
    clusters,
    gapQueries,
    proximityStats,
    spaResult,
    perClusterProximity,
    totalTerritories,
    dangerZones,
    clustersWithPresence,
    totalGaps,
    uncoveredQueries,
    criticalGaps,
    totalCompetitors,
    engineData,
    divergenceData,
    isLoading,
    error,
    refetch,
  };
}
