'use client';

import { useState, useCallback, useMemo, useEffect } from 'react';
import { Button, Badge, TabBar, EmptyState, Skeleton, Toast } from '@/components/ui';
import { BarChart3, Check, MessageSquare } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useTaxonomy, useMatrix } from '@/lib/hooks/useTopicDiscovery';
import { useTaskStream } from '@/lib/hooks/useTaskStream';
import { apiPost } from '@/lib/api/client';
import { TOPIC_DISCOVERY, CONTENT_ENGINE } from '@/lib/api/endpoints';
import { TaxonomyTree } from './_components/TaxonomyTree';
import { SubdomainDetail } from './_components/SubdomainDetail';
import { AssignmentsView } from './_components/AssignmentsView';
import { CoveragePanel } from './_components/CoveragePanel';
import {
  type SubdomainNode,
  type CategoryNode,
  type SortDimension,
  type Assignment,
} from './_components/topic-data';

type RightTab = 'detail' | 'assignments';

export default function TopicDiscoveryPage() {
  const slug = useAuthStore((s) => s.company?.slug);
  const { data: taxonomyData, isLoading: taxLoading, refetch: refetchTaxonomy } = useTaxonomy(slug);
  const { data: matrixData, refetch: refetchMatrix } = useMatrix(slug);

  const [selectedSub, setSelectedSub] = useState<SubdomainNode | null>(null);
  const [selectedCat, setSelectedCat] = useState<CategoryNode | null>(null);
  const [activeTab, setActiveTab] = useState<RightTab>('detail');
  const [coverageOpen, setCoverageOpen] = useState(false);
  const [sortDimension, setSortDimension] = useState<SortDimension>('return');

  const companyName = useAuthStore((s) => s.company?.name) ?? '';
  const companyDomain = useAuthStore((s) => s.company?.domain) ?? '';

  // Pipeline B expansion state
  const [expandingSubdomainId, setExpandingSubdomainId] = useState<string | null>(null);
  const [expandTaskId, setExpandTaskId] = useState<string | null>(null);
  const expandStream = useTaskStream(expandTaskId);

  const handleExpandTopics = useCallback(async (subdomainId: string) => {
    if (!slug || !companyName || !companyDomain) return;
    setExpandingSubdomainId(subdomainId);
    try {
      const res = await apiPost<{ run_id: string }>(TOPIC_DISCOVERY.expand, {
        company_name: companyName,
        domain: companyDomain,
        subdomain_ids: [subdomainId],
        auto_approve_checkpoints: [2],
      });
      setExpandTaskId(res.run_id);
    } catch {
      setExpandingSubdomainId(null);
    }
  }, [slug, companyName, companyDomain]);

  // React to expansion task completion
  useEffect(() => {
    if (expandStream.status === 'completed') {
      refetchMatrix();
      refetchTaxonomy();
      setExpandingSubdomainId(null);
      setExpandTaskId(null);
    } else if (expandStream.status === 'error') {
      setExpandingSubdomainId(null);
      setExpandTaskId(null);
    }
  }, [expandStream.status, refetchMatrix, refetchTaxonomy]);

  // Content engine state
  const [sendingAssignmentId, setSendingAssignmentId] = useState<string | null>(null);
  const [contentTaskId, setContentTaskId] = useState<string | null>(null);
  const [contentToast, setContentToast] = useState<{ open: boolean; variant: 'success' | 'error'; message: string }>({ open: false, variant: 'success', message: '' });
  const contentStream = useTaskStream(contentTaskId);

  const handleSendToContentEngine = useCallback(async (assignment: Assignment) => {
    if (!slug || !companyName || !companyDomain) return;
    setSendingAssignmentId(assignment.id);
    try {
      // Topic Discovery → Content pipeline handles brief creation internally.
      // No pre-creation needed (avoids dual brief_id problem).
      let pipelineStarted = false;
      try {
        const res = await apiPost<{ run_id: string }>(CONTENT_ENGINE.fromTopics, {
          company_name: companyName,
          domain: companyDomain,
          effective_slug: slug,
          topic_assignment_ids: [assignment.id],
        });
        setContentTaskId(res.run_id);
        pipelineStarted = true;
      } catch {
        // Pipeline may fail (409 etc.)
      }

      setSendingAssignmentId(null);
      setContentToast({
        open: true,
        variant: pipelineStarted ? 'success' : 'error',
        message: pipelineStarted
          ? 'Pipeline started. Topic will appear in Content Studio.'
          : 'Failed to start pipeline.',
      });
    } catch (err: unknown) {
      setSendingAssignmentId(null);
      const message = err instanceof Error ? err.message : 'Failed to add topic.';
      setContentToast({ open: true, variant: 'error', message });
    }
  }, [slug, companyName, companyDomain]);

  useEffect(() => {
    if (contentStream.status === 'completed') {
      refetchMatrix();
      setSendingAssignmentId(null);
      setContentTaskId(null);
    } else if (contentStream.status === 'error') {
      setSendingAssignmentId(null);
      setContentTaskId(null);
      setContentToast({ open: true, variant: 'error', message: 'Content pipeline failed.' });
    }
  }, [contentStream.status, refetchMatrix]);

  const taxonomyVersion = taxonomyData?.version ?? 0;

  // Parse taxonomy root_nodes from API response (Dict[str, Any])
  const categories = useMemo<CategoryNode[]>(() => {
    if (!taxonomyData?.taxonomy) return [];
    const tax = taxonomyData.taxonomy;
    // The taxonomy response wraps root_nodes in the taxonomy dict
    if (Array.isArray(tax.root_nodes)) return tax.root_nodes;
    if (Array.isArray(tax)) return tax;
    return [];
  }, [taxonomyData]);

  // Build assignment lookup by subdomain_id from matrix API
  const assignmentsBySubdomain = useMemo(() => {
    const map = new Map<string, Assignment[]>();
    if (!matrixData?.matrix) return map;
    const matrixObj = matrixData.matrix as { assignments?: Assignment[] };
    const allAssignments: Assignment[] = matrixObj.assignments ?? [];
    for (const a of allAssignments) {
      if (!map.has(a.subdomain_id)) {
        map.set(a.subdomain_id, []);
      }
      map.get(a.subdomain_id)!.push(a);
    }
    return map;
  }, [matrixData]);

  // Sync selectedSub with refreshed taxonomy data (e.g. after expansion updates expansion_status)
  useEffect(() => {
    if (!selectedSub || categories.length === 0) return;
    for (const cat of categories) {
      const found = cat.children.find((s) => s.id === selectedSub.id);
      if (found) {
        setSelectedSub(found);
        setSelectedCat(cat);
        break;
      }
    }
  }, [categories]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSelectSubdomain = useCallback(
    (sub: SubdomainNode, cat: CategoryNode) => {
      setSelectedSub(sub);
      setSelectedCat(cat);
      setActiveTab('detail');
    },
    []
  );

  const handleViewAssignments = useCallback(() => {
    setActiveTab('assignments');
  }, []);

  // Get assignments for selected subdomain
  const selectedAssignments = useMemo(() => {
    if (!selectedSub) return [];
    return assignmentsBySubdomain.get(selectedSub.id) ?? [];
  }, [selectedSub, assignmentsBySubdomain]);

  const tabs = [
    { id: 'detail', label: 'Subdomain Detail' },
    {
      id: 'assignments',
      label: `Assignments (${selectedAssignments.length})`,
    },
  ];

  if (taxLoading) {
    return (
      <div className="flex flex-col h-full -m-4">
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
          <Skeleton className="h-8 w-60 rounded-md" />
        </div>
        <div className="flex flex-1">
          <div className="w-[380px] border-r border-border p-3">
            <Skeleton className="h-full rounded-md" />
          </div>
          <div className="flex-1 p-4">
            <Skeleton className="h-full rounded-md" />
          </div>
        </div>
      </div>
    );
  }

  if (categories.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-[14px] text-text-secondary mb-2">No taxonomy data yet</p>
        <p className="text-[12px] text-text-tertiary">Run the topic discovery pipeline to generate a taxonomy.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full -m-4">
      {/* Global Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border shrink-0">
        <div className="flex items-center gap-3">
          <div>
            <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block">
              Topic Discovery
            </span>
            <span className="text-[16px] font-semibold text-text-primary tracking-[-0.01em]">
              {companyName} / Pipeline A + B
            </span>
          </div>

          {selectedSub && activeTab === 'detail' && (
            <Badge variant="warning">HITL-1 Pending</Badge>
          )}
          {selectedSub && activeTab === 'assignments' && (
            <Badge variant="warning">HITL-2 Pending</Badge>
          )}
          <Badge variant="neutral">v{taxonomyVersion}</Badge>
          <Badge variant="info">{taxonomyData?.total_subdomains ?? 0} subdomains</Badge>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant={coverageOpen ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setCoverageOpen(!coverageOpen)}
          >
            <BarChart3 size={11} strokeWidth={1.5} className="mr-1" />
            Coverage ({((taxonomyData?.coverage_score ?? 0) * 100).toFixed(0)}%)
          </Button>
          <Button variant="ghost" size="sm" className="bg-success-subtle text-success hover:bg-success/10">
            <Check size={11} strokeWidth={1.5} className="mr-1" />
            Approve
          </Button>
          <Button variant="secondary" size="sm">
            <MessageSquare size={11} strokeWidth={1.5} className="mr-1" />
            Request Changes
          </Button>
        </div>
      </div>

      {/* Coverage Panel */}
      <CoveragePanel
        open={coverageOpen}
        coverageScore={taxonomyData?.coverage_score}
        totalSubdomains={taxonomyData?.total_subdomains}
      />

      {/* Main Content: Tree + Right Panel */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Taxonomy Tree */}
        <div className="w-[380px] shrink-0 border-r border-border overflow-hidden">
          <TaxonomyTree
            selectedSubdomainId={selectedSub?.id ?? null}
            onSelectSubdomain={handleSelectSubdomain}
            sortDimension={sortDimension}
            onSortChange={setSortDimension}
            categories={categories}
            assignmentsBySubdomain={assignmentsBySubdomain}
          />
        </div>

        {/* Right: Detail or Assignments */}
        <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
          {selectedSub && selectedCat ? (
            <>
              <TabBar
                tabs={tabs}
                activeTab={activeTab}
                onTabClick={(id) => setActiveTab(id as RightTab)}
              />

              {activeTab === 'detail' ? (
                <SubdomainDetail
                  subdomain={selectedSub}
                  category={selectedCat}
                  onViewAssignments={handleViewAssignments}
                  assignments={selectedAssignments}
                  scoring={undefined}
                  companyName={companyName}
                  onExpandTopics={handleExpandTopics}
                  expandingSubdomainId={expandingSubdomainId}
                />
              ) : (
                <AssignmentsView
                  subdomain={selectedSub}
                  assignments={selectedAssignments}
                  onSendToContentEngine={handleSendToContentEngine}
                  sendingAssignmentId={sendingAssignmentId}
                />
              )}
            </>
          ) : (
            <EmptyState
              title="Select a subdomain"
              description="Click a subdomain in the taxonomy tree to view its detail, AEO scoring, and content assignments."
            />
          )}
        </div>
      </div>

      <Toast
        open={contentToast.open}
        onClose={() => setContentToast((t) => ({ ...t, open: false }))}
        variant={contentToast.variant}
        message={contentToast.message}
      />
    </div>
  );
}
