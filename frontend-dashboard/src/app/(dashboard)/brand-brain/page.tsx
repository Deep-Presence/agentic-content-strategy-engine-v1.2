'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  FlaskConical,
  Pencil,
  Upload,
  Plus,
  ArrowRight,
  Brain,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { useAppStore } from '@/stores/app-store';
import { useBrandStore } from '@/stores/brand-store';
import { useArtifactFiles } from '@/lib/hooks/use-artifacts';
import { artifacts } from '@/lib/api/artifacts';
import { tasks } from '@/lib/api/tasks';
import { relativeTime } from '@/lib/utils/format';
import { STATUS_COLORS } from '@/lib/utils/constants';
import { BrandOverviewCards } from './components/brand-overview-cards';
import { ProjectCard } from './components/project-card';
import { CreateProjectDialog } from './components/create-project-dialog';
import { ResearchTrigger } from './components/research-trigger';
import { ResearchProgress } from './components/research-progress';
import { ResearchApprovalInline } from './components/research-approval-inline';
import type { TaskResponse, TaskStatus } from '@/types/common';

type ArtifactStatus = 'none' | 'draft' | 'approved';

export default function BrandBrainPage() {
  const router = useRouter();
  const { toast } = useToast();
  const currentCompany = useAppStore((s) => s.currentCompany);
  const {
    companyContextStatus,
    setCompanyContext,
    personas,
    setPersonas,
    styleGuideStatus,
    setStyleGuide,
    projects,
    knowledgeDocs,
    activeResearchRunId,
    approvalPayload,
    setResearchRun,
    clearResearchRun,
    setLoading,
  } = useBrandStore();

  const [showCreateProject, setShowCreateProject] = useState(false);
  const [loading, setPageLoading] = useState(true);
  const [researchTasks, setResearchTasks] = useState<TaskResponse[]>([]);
  const [approvalStage, setApprovalStage] = useState<string | null>(null);
  const [approvalContent, setApprovalContent] = useState<string>('');

  // Track artifact statuses
  const [ctxStatus, setCtxStatus] = useState<ArtifactStatus>('none');
  const [personaStatus, setPersonaStatus] = useState<ArtifactStatus>('none');
  const [sgStatus, setSgStatus] = useState<ArtifactStatus>('none');
  const [hasKnowledgeDocs, setHasKnowledgeDocs] = useState(false);

  const companyName = currentCompany
    ? currentCompany.charAt(0).toUpperCase() + currentCompany.slice(1)
    : '';

  const loadData = useCallback(async () => {
    if (!currentCompany) return;
    setPageLoading(true);

    try {
      // Check company context
      try {
        const ctxFiles = await artifacts.listFiles('company_context', currentCompany);
        if (ctxFiles.files.length > 0) {
          setCtxStatus('approved');
          const content = await artifacts.getContent<string>(
            'company_context',
            currentCompany,
            ctxFiles.files[0]
          );
          if (content) setCompanyContext(content, 'approved');
        }
      } catch {
        setCtxStatus('none');
      }

      // Check personas
      try {
        const personaFiles = await artifacts.listFiles('personas', currentCompany);
        if (personaFiles.files.length > 0) {
          setPersonaStatus('approved');
          const loadedPersonas = [];
          for (const file of personaFiles.files) {
            try {
              const content = await artifacts.getContent<string>(
                'personas',
                currentCompany,
                file
              );
              if (content) {
                loadedPersonas.push({
                  id: file,
                  name: file.replace(`${currentCompany}__`, '').replace('.md', '').replace(/-/g, ' '),
                  type: file.includes('icp') ? 'icp' as const : 'secondary' as const,
                  content: typeof content === 'string' ? content : JSON.stringify(content),
                });
              }
            } catch {
              // Skip failed files
            }
          }
          if (loadedPersonas.length > 0) setPersonas(loadedPersonas);
        }
      } catch {
        setPersonaStatus('none');
      }

      // Check style guide
      try {
        const sgFiles = await artifacts.listFiles('style_guides', currentCompany);
        if (sgFiles.files.length > 0) {
          setSgStatus('approved');
          const content = await artifacts.getContent<string>(
            'style_guides',
            currentCompany,
            sgFiles.files[0]
          );
          if (content) setStyleGuide(typeof content === 'string' ? content : JSON.stringify(content), 'approved');
        }
      } catch {
        setSgStatus('none');
      }

      // Check knowledge docs
      setHasKnowledgeDocs(knowledgeDocs.length > 0);

      // Load recent research tasks
      try {
        const taskList = await tasks.list();
        const researchRuns = taskList.tasks
          .filter((t) => t.pipeline === 'research')
          .slice(0, 5);
        setResearchTasks(researchRuns);
      } catch {
        // Ignore
      }
    } catch {
      toast('Failed to load brand data', 'error');
    } finally {
      setPageLoading(false);
    }
  }, [currentCompany, knowledgeDocs.length, setCompanyContext, setPersonas, setStyleGuide, toast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleDraftReady = (stage: string, data: Record<string, unknown>) => {
    setApprovalStage(stage);
    const content = (data.content as string) ?? (data.draft as string) ?? '';
    setApprovalContent(content);
  };

  const handleResearchComplete = () => {
    setApprovalStage(null);
    setApprovalContent('');
    loadData();
  };

  if (loading && !currentCompany) {
    return (
      <div className="space-y-8">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-64 rounded-md" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Brand Brain"
        description={`Your AI agents' knowledge base for ${companyName}`}
        actions={
          <Button onClick={() => setShowCreateProject(true)} variant="secondary" size="sm">
            <Plus className="h-4 w-4 mr-1.5" />
            New Project
          </Button>
        }
      />

      {/* Knowledge Completeness */}
      {loading ? (
        <Skeleton className="h-48 rounded-md" />
      ) : (
        <BrandOverviewCards
          companyContextStatus={ctxStatus}
          personaStatus={personaStatus}
          styleGuideStatus={sgStatus}
          hasKnowledgeDocs={hasKnowledgeDocs}
        />
      )}

      {/* Active Research Pipeline */}
      {activeResearchRunId && (
        <div className="space-y-4">
          <ResearchProgress
            runId={activeResearchRunId}
            onDraftReady={handleDraftReady}
            onComplete={handleResearchComplete}
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

      {/* Quick Actions */}
      <div>
        <h3 className="font-serif text-heading-3 font-semibold text-cream-950 mb-4">
          Quick Actions
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <ResearchTrigger
            mode="full"
            companySlug={currentCompany}
            companyName={companyName}
            domain={`${currentCompany}.com`}
            onStarted={(runId) => {
              setResearchRun(runId, 'running', 'company');
            }}
          />
          <button
            onClick={() => router.push('/brand-brain/style-guide')}
            className="flex items-center gap-3 p-4 bg-white rounded-md border border-[var(--border-default)] hover:shadow-[var(--shadow-md)] hover:-translate-y-px transition-all text-left"
          >
            <Pencil className="h-5 w-5 text-terracotta-400" />
            <div>
              <span className="font-sans text-body-sm font-medium text-cream-900 block">
                Edit Style Guide
              </span>
              <span className="font-sans text-caption text-cream-600">
                View or modify writing guidelines
              </span>
            </div>
          </button>
          <button
            onClick={() => router.push('/brand-brain/knowledge')}
            className="flex items-center gap-3 p-4 bg-white rounded-md border border-[var(--border-default)] hover:shadow-[var(--shadow-md)] hover:-translate-y-px transition-all text-left"
          >
            <Upload className="h-5 w-5 text-terracotta-400" />
            <div>
              <span className="font-sans text-body-sm font-medium text-cream-900 block">
                Upload Brand Docs
              </span>
              <span className="font-sans text-caption text-cream-600">
                Add knowledge documents
              </span>
            </div>
          </button>
        </div>
      </div>

      {/* Projects */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-serif text-heading-3 font-semibold text-cream-950">
            Projects ({projects.length})
          </h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowCreateProject(true)}
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            Create Project
          </Button>
        </div>
        {projects.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center bg-white rounded-md border border-[var(--border-default)]">
            <Brain className="h-10 w-10 text-cream-500 mb-3" />
            <p className="text-body text-cream-600 mb-4">
              No projects yet. Create a product-level knowledge base.
            </p>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowCreateProject(true)}
            >
              <Plus className="h-3.5 w-3.5 mr-1.5" />
              Create Project
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => (
              <ProjectCard key={project.id} project={project} />
            ))}
          </div>
        )}
      </div>

      {/* Recent Research Runs */}
      <div>
        <h3 className="font-serif text-heading-3 font-semibold text-cream-950 mb-4">
          Recent Research Runs
        </h3>
        {loading ? (
          <Skeleton className="h-40 rounded-md" />
        ) : researchTasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center bg-white rounded-md border border-[var(--border-default)]">
            <FlaskConical className="h-8 w-8 text-cream-500 mb-2" />
            <p className="text-body-sm text-cream-600">No research runs yet.</p>
          </div>
        ) : (
          <div className="bg-white rounded-md border border-[var(--border-default)] overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Company</TableHead>
                  <TableHead>Current Step</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {researchTasks.map((task) => (
                  <TableRow key={task.run_id}>
                    <TableCell className="font-medium text-cream-900">
                      {task.company_slug}
                    </TableCell>
                    <TableCell className="text-cream-700">
                      {task.current_step ?? '—'}
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={STATUS_COLORS[task.status] ?? STATUS_COLORS.pending}
                      >
                        {task.status.replace(/_/g, ' ')}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-cream-600">
                      {relativeTime(task.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm">
                        View <ArrowRight className="h-3 w-3 ml-1" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      <CreateProjectDialog
        open={showCreateProject}
        onClose={() => setShowCreateProject(false)}
      />
    </div>
  );
}
