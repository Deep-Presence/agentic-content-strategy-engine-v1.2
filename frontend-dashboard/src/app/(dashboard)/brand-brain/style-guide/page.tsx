'use client';

import { useState, useEffect, useCallback } from 'react';
import { PageHeader } from '@/components/layout/page-header';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { useAppStore } from '@/stores/app-store';
import { useBrandStore } from '@/stores/brand-store';
import { artifacts } from '@/lib/api/artifacts';
import { StyleGuideViewer } from '../components/style-guide-viewer';
import { ResearchTrigger } from '../components/research-trigger';
import { ResearchProgress } from '../components/research-progress';
import { ResearchApprovalInline } from '../components/research-approval-inline';

export default function StyleGuidePage() {
  const { toast } = useToast();
  const currentCompany = useAppStore((s) => s.currentCompany);
  const {
    styleGuide,
    styleGuideStatus,
    setStyleGuide,
    activeResearchRunId,
    setResearchRun,
  } = useBrandStore();

  const [loading, setLoading] = useState(true);
  const [approvalStage, setApprovalStage] = useState<string | null>(null);
  const [approvalContent, setApprovalContent] = useState('');
  const [showTrigger, setShowTrigger] = useState(false);

  const companyName = currentCompany
    ? currentCompany.charAt(0).toUpperCase() + currentCompany.slice(1)
    : '';

  const loadStyleGuide = useCallback(async () => {
    if (!currentCompany) return;
    setLoading(true);

    try {
      const sgFiles = await artifacts.listFiles('style_guides', currentCompany);
      if (sgFiles.files.length > 0) {
        const content = await artifacts.getContent<string>(
          'style_guides',
          currentCompany,
          sgFiles.files[0]
        );
        if (content) {
          setStyleGuide(
            typeof content === 'string' ? content : JSON.stringify(content),
            'approved'
          );
        }
      }
    } catch {
      // No style guide
    } finally {
      setLoading(false);
    }
  }, [currentCompany, setStyleGuide]);

  useEffect(() => {
    loadStyleGuide();
  }, [loadStyleGuide]);

  const handleGenerate = () => {
    setShowTrigger(true);
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="Style Guide"
        description={`Writing style guide for ${companyName}`}
        actions={
          !showTrigger && !activeResearchRunId ? (
            <ResearchTrigger
              mode="style"
              companySlug={currentCompany}
              companyName={companyName}
              domain={`${currentCompany}.com`}
              onStarted={(runId) => {
                setResearchRun(runId, 'running', 'style_guide');
                setShowTrigger(false);
              }}
            />
          ) : undefined
        }
      />

      {/* Active Research Pipeline */}
      {activeResearchRunId && (
        <div className="space-y-4">
          <ResearchProgress
            runId={activeResearchRunId}
            onDraftReady={(stage, data) => {
              setApprovalStage(stage);
              setApprovalContent(
                (data.content as string) ?? (data.draft as string) ?? ''
              );
            }}
            onComplete={() => {
              setApprovalStage(null);
              setApprovalContent('');
              loadStyleGuide();
            }}
          />
          {approvalStage && approvalContent && (
            <ResearchApprovalInline
              runId={activeResearchRunId}
              stage={approvalStage}
              draftContent={approvalContent}
              onApproved={() => {
                setApprovalStage(null);
                setApprovalContent('');
              }}
              onRevised={() => {
                setApprovalStage(null);
                setApprovalContent('');
              }}
              onRejected={() => {
                setApprovalStage(null);
                setApprovalContent('');
              }}
            />
          )}
        </div>
      )}

      {/* Style Guide Content */}
      {loading ? (
        <Skeleton className="h-96 rounded-md" />
      ) : (
        <StyleGuideViewer
          content={styleGuide}
          status={styleGuideStatus}
          onEdit={(newContent) => {
            setStyleGuide(newContent, 'approved');
            toast('Style guide updated', 'success');
          }}
          onGenerate={handleGenerate}
        />
      )}
    </div>
  );
}
