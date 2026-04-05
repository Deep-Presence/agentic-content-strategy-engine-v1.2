'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/lib/api-client';
import type { Assignment, Cluster, RejectedItem } from '../_components/planner-data';
import { deriveCompanyPrefix, formatDisplayId, formatPersonaName } from '../_components/planner-data';
import type { DiscoverySummaryResponseAPI, SubdomainNodeAPI } from '../_lib/types';
import {
  fetchDiscoverySummary,
  fetchAssignments,
  fetchTaxonomy,
  fetchPersonaAffinity,
  updateAssignmentStatus,
  createCustomAssignment,
  expandSubdomain as expandSubdomainApi,
} from '../_lib/api';
import { adaptAssignments, buildTaxonomyMap, buildClusters, adaptRejectedItem } from '../_lib/adapters';

// ── Public types ────────────────────────────────────────

export interface CreateCustomAssignmentData {
  topic_text: string;
  subdomain_name?: string;
  buyer_stage?: string;
  intent_type?: string;
  persona_id?: string;
  persona_name?: string;
  priority_score?: number;
}

export interface PlannerData {
  assignments: Assignment[];
  rejected: RejectedItem[];
  clusters: Cluster[];
  summary: DiscoverySummaryResponseAPI | null;
  /** Dynamic persona_id → display name map (built from API data) */
  personaNames: Record<string, string>;
  isLoading: boolean;
  error: string | null;
  isEmpty: boolean;
  refetch: () => void;
  approveAssignments: (ids: string[]) => Promise<void>;
  rejectAssignments: (ids: string[]) => Promise<void>;
  restoreAssignment: (id: string) => Promise<void>;
  createAssignment: (data: CreateCustomAssignmentData) => Promise<void>;
  expandSubdomain: (subdomainId: string) => Promise<{ runId: string }>;
}

// ── Hook ────────────────────────────────────────────────

export function usePlannerData(): PlannerData {
  const { companySlug, companyName, companyDomain, isInitialized } = useAuth();

  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [rejected, setRejected] = useState<RejectedItem[]>([]);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [summary, setSummary] = useState<DiscoverySummaryResponseAPI | null>(null);
  const [personaNames, setPersonaNames] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEmpty, setIsEmpty] = useState(false);

  // Keep taxonomy root nodes in a ref for adapter use in mutations
  const rootNodesRef = useRef<SubdomainNodeAPI[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  // ── Load data ───────────────────────────────────────

  // Derive prefix once from companyName (stable across loadData calls)
  const prefixRef = useRef('DP');

  const loadData = useCallback(async (slug: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const signal = controller.signal;

    setIsLoading(true);
    setError(null);
    setIsEmpty(false);

    try {
      // Phase 1: Fetch summary to check if discovery data exists
      const summaryData = await fetchDiscoverySummary(slug, signal);
      if (signal.aborted) return;

      setSummary(summaryData);

      if (!summaryData.has_matrix) {
        setIsEmpty(true);
        setAssignments([]);
        setRejected([]);
        setClusters([]);
        setIsLoading(false);
        return;
      }

      // Phase 2: Fetch assignments, taxonomy, and persona affinity in parallel
      const [assignmentsResult, taxonomyResult, affinityResult] = await Promise.allSettled([
        fetchAssignments(slug, { page_size: 500 }, signal),
        fetchTaxonomy(slug, signal),
        fetchPersonaAffinity(slug, signal),
      ]);

      if (signal.aborted) return;

      const assignmentsData =
        assignmentsResult.status === 'fulfilled' ? assignmentsResult.value : null;
      const taxonomyData =
        taxonomyResult.status === 'fulfilled' ? taxonomyResult.value : null;
      const affinityData =
        affinityResult.status === 'fulfilled' ? affinityResult.value : null;

      // Store root nodes for mutation adapters
      const rootNodes = taxonomyData?.taxonomy?.root_nodes ?? [];
      rootNodesRef.current = rootNodes;

      // Build clusters from taxonomy
      setClusters(buildClusters(rootNodes));

      // Adapt assignments
      const allItems = assignmentsData?.items ?? [];
      const personaEntries = affinityData?.persona_entries ?? {};
      const matrixCreatedAt = summaryData.last_updated;

      const adapted = adaptAssignments(allItems, rootNodes, personaEntries, matrixCreatedAt);

      // Build dynamic persona name map from persona_metadata + affinity keys
      const pNames: Record<string, string> = {};
      const pMeta = affinityData?.persona_metadata ?? {};
      for (const pid of Object.keys(personaEntries)) {
        const meta = pMeta[pid];
        if (meta?.persona_name && meta?.career_role) {
          pNames[pid] = `${meta.persona_name} — ${meta.career_role}`;
        } else if (meta?.persona_name) {
          pNames[pid] = meta.persona_name;
        } else {
          pNames[pid] = formatPersonaName(pid);
        }
      }
      // Also pick up names from assignments (in case affinity data is missing)
      for (const item of allItems) {
        if (item.persona_id && item.persona_name && !pNames[item.persona_id]) {
          pNames[item.persona_id] = item.persona_name;
        }
      }
      setPersonaNames(pNames);

      // Split into active vs rejected
      const taxonomyMap = buildTaxonomyMap(rootNodes);
      const active: Assignment[] = [];
      const rejectedItems: RejectedItem[] = [];

      for (let i = 0; i < allItems.length; i++) {
        if (allItems[i].status === 'rejected') {
          rejectedItems.push(adaptRejectedItem(allItems[i], taxonomyMap));
        } else {
          active.push(adapted[i]);
        }
      }

      // Assign human-readable displayIds: sort by createdAt, then sequential
      const prefix = prefixRef.current;
      const sortedActive = [...active].sort((a, b) => a.createdAt.localeCompare(b.createdAt));
      const idLookup = new Map<string, string>();
      sortedActive.forEach((a, i) => idLookup.set(a.id, formatDisplayId(prefix, i + 1)));
      for (const a of active) {
        a.displayId = idLookup.get(a.id) ?? a.id;
      }

      setAssignments(active);
      setRejected(rejectedItems);

      // Check if all fetches failed
      const allFailed =
        assignmentsResult.status === 'rejected' &&
        taxonomyResult.status === 'rejected' &&
        affinityResult.status === 'rejected';

      if (allFailed) {
        const firstErr =
          assignmentsResult.status === 'rejected' ? assignmentsResult.reason : null;
        if (firstErr instanceof ApiError && firstErr.status !== 404) {
          setError(firstErr.detail);
        } else {
          setError('Unable to load planner data. Please try again.');
        }
      }
    } catch (err) {
      if (signal.aborted) return;
      if (err instanceof ApiError) {
        if (err.status === 404) {
          setIsEmpty(true);
        } else {
          setError(err.detail);
        }
      } else {
        setError('Unable to load planner data. Please try again.');
      }
    } finally {
      if (!signal.aborted) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    if (!isInitialized || !companySlug) return;
    if (companyName) prefixRef.current = deriveCompanyPrefix(companyName);
    loadData(companySlug);
    return () => {
      abortRef.current?.abort();
    };
  }, [isInitialized, companySlug, companyName, loadData]);

  const refetch = useCallback(() => {
    if (companySlug) loadData(companySlug);
  }, [companySlug, loadData]);

  // ── Optimistic mutations ──────────────────────────────

  const approveAssignments = useCallback(
    async (ids: string[]) => {
      if (!companySlug) return;
      const idSet = new Set(ids);

      // Optimistic: just keep them in active list (status change is invisible in UI)
      const prevAssignments = assignments;

      // Fire API calls in background
      const results = await Promise.allSettled(
        ids.map((id) => updateAssignmentStatus(companySlug, id, 'approved')),
      );

      const failed = results.filter((r) => r.status === 'rejected');
      if (failed.length > 0) {
        // Rollback — restore previous state
        setAssignments(prevAssignments);
        throw new Error(
          `Failed to approve ${failed.length} of ${ids.length} assignment(s).`,
        );
      }
    },
    [companySlug, assignments],
  );

  const rejectAssignments = useCallback(
    async (ids: string[]) => {
      if (!companySlug) return;
      const idSet = new Set(ids);

      // Optimistic: move from active to rejected
      const toReject = assignments.filter((a) => idSet.has(a.id));
      const remaining = assignments.filter((a) => !idSet.has(a.id));
      const newRejected: RejectedItem[] = toReject.map((a) => ({
        id: a.id,
        title: a.title,
        cluster: a.cluster,
        reason: 'Rejected by user',
        date: new Date().toISOString(),
        rejectedBy: 'User',
        stage: a.stage,
      }));

      setAssignments(remaining);
      setRejected((prev) => [...prev, ...newRejected]);

      // Fire API calls in background
      const results = await Promise.allSettled(
        ids.map((id) => updateAssignmentStatus(companySlug, id, 'rejected')),
      );

      const failed = results.filter((r) => r.status === 'rejected');
      if (failed.length > 0) {
        // Rollback
        setAssignments(assignments);
        setRejected((prev) => prev.filter((r) => !idSet.has(r.id)));
        throw new Error(
          `Failed to reject ${failed.length} of ${ids.length} assignment(s).`,
        );
      }
    },
    [companySlug, assignments],
  );

  const restoreAssignment = useCallback(
    async (id: string) => {
      if (!companySlug) return;

      // Find the rejected item
      const item = rejected.find((r) => r.id === id);
      if (!item) return;

      // Optimistic: move from rejected back to active
      setRejected((prev) => prev.filter((r) => r.id !== id));

      // Create a minimal Assignment for the restored item
      const restored: Assignment = {
        id: item.id,
        displayId: formatDisplayId(prefixRef.current, assignments.length + 1),
        title: item.title,
        description: '',
        cluster: item.cluster,
        subcluster: '',
        stage: item.stage ?? 'TOFU',
        intent: 'Informational',
        format: null,
        source: 'gap',
        initiative: undefined,
        personaScores: {},
        persona: '',
        citationOpp: 0,
        priorityScore: 0,
        effort: null,
        estDays: null,
        wordCount: null,
        contentFormat: null,
        targetKeywords: { primary: '', secondary: [] },
        reasons: [],
        relatedQueries: [],
        createdAt: new Date().toISOString(),
        activityLog: [
          { action: 'Restored from rejected', date: new Date().toISOString(), by: 'User' },
        ],
        priorityFactors: {},
      };
      setAssignments((prev) => [...prev, restored]);

      try {
        await updateAssignmentStatus(companySlug, id, 'not_started');
      } catch {
        // Rollback
        setAssignments((prev) => prev.filter((a) => a.id !== id));
        setRejected((prev) => [...prev, item]);
        throw new Error('Failed to restore assignment.');
      }
    },
    [companySlug, rejected],
  );

  const createAssignment = useCallback(
    async (data: CreateCustomAssignmentData) => {
      if (!companySlug) return;

      const created = await createCustomAssignment(companySlug, data);

      // Adapt the newly created assignment and add to list
      const taxonomyMap = buildTaxonomyMap(rootNodesRef.current);
      const newAssignment: Assignment = {
        id: created.id,
        displayId: formatDisplayId(prefixRef.current, assignments.length + rejected.length + 1),
        title: created.topic_text,
        description: '',
        cluster: taxonomyMap.get(created.subdomain_id)?.clusterName ?? 'Uncategorized',
        subcluster: created.subdomain_name,
        stage: created.buyer_stage.toUpperCase() as 'TOFU' | 'MOFU' | 'BOFU',
        intent: (created.intent_type.charAt(0).toUpperCase() +
          created.intent_type.slice(1)) as Assignment['intent'],
        format: null,
        source: 'custom',
        initiative: undefined,
        personaScores: {},
        persona: created.persona_id,
        citationOpp: created.priority_score,
        priorityScore: created.priority_score,
        effort: null,
        estDays: null,
        wordCount: null,
        contentFormat: null,
        targetKeywords: { primary: '', secondary: [] },
        reasons: [],
        relatedQueries: [],
        createdAt: new Date().toISOString(),
        activityLog: [
          { action: 'Manually created', date: new Date().toISOString(), by: 'User' },
        ],
        priorityFactors: {},
      };

      setAssignments((prev) => [newAssignment, ...prev]);
    },
    [companySlug],
  );

  const expandSubdomain = useCallback(
    async (subdomainId: string): Promise<{ runId: string }> => {
      if (!companyName || !companyDomain) {
        throw new Error('Company info not available. Please try again.');
      }
      const result = await expandSubdomainApi(companyName, companyDomain, [subdomainId], {
        auto_approve_checkpoints: [2],
        taxonomy_version: summary?.taxonomy_version,
      });
      return { runId: result.run_id };
    },
    [companyName, companyDomain, summary?.taxonomy_version],
  );

  // ── Return ────────────────────────────────────────────

  return {
    assignments,
    rejected,
    clusters,
    summary,
    personaNames,
    isLoading,
    error,
    isEmpty,
    refetch,
    approveAssignments,
    rejectAssignments,
    restoreAssignment,
    createAssignment,
    expandSubdomain,
  };
}
