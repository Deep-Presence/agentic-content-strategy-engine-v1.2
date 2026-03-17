'use client';

import { useState, useCallback } from 'react';
import { Button, Badge, TabBar, EmptyState } from '@/components/ui';
import { BarChart3, Check, MessageSquare } from 'lucide-react';
import { TaxonomyTree } from './_components/TaxonomyTree';
import { SubdomainDetail } from './_components/SubdomainDetail';
import { AssignmentsView } from './_components/AssignmentsView';
import { CoveragePanel } from './_components/CoveragePanel';
import {
  type SubdomainNode,
  type CategoryNode,
  type SortDimension,
  companyName,
  taxonomyVersion,
  getAssignments,
} from './_components/topic-data';

type RightTab = 'detail' | 'assignments';

export default function TopicDiscoveryPage() {
  const [selectedSub, setSelectedSub] = useState<SubdomainNode | null>(null);
  const [selectedCat, setSelectedCat] = useState<CategoryNode | null>(null);
  const [activeTab, setActiveTab] = useState<RightTab>('detail');
  const [coverageOpen, setCoverageOpen] = useState(false);
  const [sortDimension, setSortDimension] = useState<SortDimension>('return');

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

  const assignments = selectedSub ? getAssignments(selectedSub.id) : [];

  const tabs = [
    { id: 'detail', label: 'Subdomain Detail' },
    {
      id: 'assignments',
      label: `Assignments (${assignments.length})`,
    },
  ];

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

          {/* Status badges */}
          {selectedSub && activeTab === 'detail' && (
            <Badge variant="warning">HITL-1 Pending</Badge>
          )}
          {selectedSub && activeTab === 'assignments' && (
            <Badge variant="warning">HITL-2 Pending</Badge>
          )}
          <Badge variant="neutral">v{taxonomyVersion}</Badge>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant={coverageOpen ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setCoverageOpen(!coverageOpen)}
          >
            <BarChart3 size={11} strokeWidth={1.5} className="mr-1" />
            Coverage
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
      <CoveragePanel open={coverageOpen} />

      {/* Main Content: Tree + Right Panel */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Taxonomy Tree */}
        <div className="w-[380px] shrink-0 border-r border-border overflow-hidden">
          <TaxonomyTree
            selectedSubdomainId={selectedSub?.id ?? null}
            onSelectSubdomain={handleSelectSubdomain}
            sortDimension={sortDimension}
            onSortChange={setSortDimension}
          />
        </div>

        {/* Right: Detail or Assignments */}
        <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
          {selectedSub && selectedCat ? (
            <>
              {/* Tab Bar */}
              <TabBar
                tabs={tabs}
                activeTab={activeTab}
                onTabClick={(id) => setActiveTab(id as RightTab)}
              />

              {/* Tab Content */}
              {activeTab === 'detail' ? (
                <SubdomainDetail
                  subdomain={selectedSub}
                  category={selectedCat}
                  onViewAssignments={handleViewAssignments}
                />
              ) : (
                <AssignmentsView
                  subdomain={selectedSub}
                  assignments={assignments}
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
    </div>
  );
}
