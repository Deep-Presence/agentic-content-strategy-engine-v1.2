'use client';

import { createContext, useContext } from 'react';
import type {
  ClusterProfile,
  DivergenceRow,
  EngineData,
  GapQuery,
  ProximityStats,
  SPAResult,
} from './data';

export interface EmbeddingLabContextValue {
  clusterProfiles: Record<string, ClusterProfile>;
  clusters: ClusterProfile[];
  gapQueries: GapQuery[];
  proximityStats: ProximityStats;
  spaResult: SPAResult;
  perClusterProximity: Record<string, { mean: number; std: number; min: number; max: number; count: number }>;
  totalTerritories: number;
  dangerZones: number;
  clustersWithPresence: number;
  totalGaps: number;
  uncoveredQueries: number;
  criticalGaps: number;
  totalCompetitors: number;
  engineData: EngineData[];
  divergenceData: DivergenceRow[];
}

const EmbeddingLabContext = createContext<EmbeddingLabContextValue | null>(null);

export const EmbeddingLabProvider = EmbeddingLabContext.Provider;

export function useEmbeddingLabContext(): EmbeddingLabContextValue {
  const ctx = useContext(EmbeddingLabContext);
  if (!ctx) {
    throw new Error('useEmbeddingLabContext must be used within EmbeddingLabProvider');
  }
  return ctx;
}
