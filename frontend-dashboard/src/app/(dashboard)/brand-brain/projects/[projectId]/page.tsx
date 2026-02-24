'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Users,
  BookOpen,
  Image,
  Settings,
  Plus,
  Trash2,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { useToast } from '@/components/ui/toast';
import { useBrandStore } from '@/stores/brand-store';
import { PersonaCard } from '../../components/persona-card';
import { PersonaEditor } from '../../components/persona-editor';
import { StyleGuideViewer } from '../../components/style-guide-viewer';
import { KnowledgeDocCard } from '../../components/knowledge-doc-card';
import { KnowledgeDocEditor } from '../../components/knowledge-doc-editor';
import { ResearchTrigger } from '../../components/research-trigger';
import { ResearchProgress } from '../../components/research-progress';
import { ResearchApprovalInline } from '../../components/research-approval-inline';
import type { Persona, KnowledgeDoc, Project } from '@/types/brand';

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const projectId = params.projectId as string;

  const {
    projects,
    setProjects,
    removeProject,
    activeResearchRunId,
    setResearchRun,
  } = useBrandStore();

  const project = projects.find((p) => p.id === projectId);

  const [personaEditorOpen, setPersonaEditorOpen] = useState(false);
  const [editingPersona, setEditingPersona] = useState<Persona | undefined>();
  const [docEditorOpen, setDocEditorOpen] = useState(false);
  const [editingDoc, setEditingDoc] = useState<KnowledgeDoc | undefined>();
  const [approvalStage, setApprovalStage] = useState<string | null>(null);
  const [approvalContent, setApprovalContent] = useState('');
  const [projectName, setProjectName] = useState(project?.name ?? '');
  const [projectDescription, setProjectDescription] = useState(
    project?.description ?? ''
  );

  if (!project) {
    return (
      <div className="space-y-8">
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <h2 className="font-serif text-heading-3 text-cream-800 mb-2">
            Project Not Found
          </h2>
          <p className="text-body text-cream-600 mb-4">
            This project doesn&apos;t exist or has been deleted.
          </p>
          <Button variant="secondary" onClick={() => router.push('/brand-brain/projects')}>
            <ArrowLeft className="h-4 w-4 mr-1.5" />
            Back to Projects
          </Button>
        </div>
      </div>
    );
  }

  const updateProject = (updates: Partial<Project>) => {
    setProjects(
      projects.map((p) => (p.id === projectId ? { ...p, ...updates } : p))
    );
  };

  const handlePersonaSave = (persona: Persona) => {
    const existingPersonas = project.personas;
    const exists = existingPersonas.find((p) => p.id === persona.id);
    const updated = exists
      ? existingPersonas.map((p) => (p.id === persona.id ? persona : p))
      : [...existingPersonas, { ...persona, project_id: projectId }];
    updateProject({ personas: updated });
    setEditingPersona(undefined);
  };

  const handlePersonaDelete = (id: string) => {
    updateProject({
      personas: project.personas.filter((p) => p.id !== id),
    });
    toast('Persona removed', 'info');
  };

  const handleDocSave = (doc: KnowledgeDoc) => {
    const existingDocs = project.knowledge_docs;
    const exists = existingDocs.find((d) => d.id === doc.id);
    const updated = exists
      ? existingDocs.map((d) => (d.id === doc.id ? doc : d))
      : [...existingDocs, { ...doc, project_id: projectId }];
    updateProject({ knowledge_docs: updated });
    setEditingDoc(undefined);
  };

  const handleDocDelete = (id: string) => {
    updateProject({
      knowledge_docs: project.knowledge_docs.filter((d) => d.id !== id),
    });
    toast('Document removed', 'info');
  };

  const handleDeleteProject = () => {
    removeProject(projectId);
    toast('Project deleted', 'info');
    router.push('/brand-brain/projects');
  };

  const handleSaveSettings = () => {
    updateProject({
      name: projectName.trim(),
      description: projectDescription.trim() || undefined,
    });
    toast('Project settings saved', 'success');
  };

  return (
    <div className="space-y-6">
      <div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push('/brand-brain/projects')}
          className="mb-2"
        >
          <ArrowLeft className="h-3.5 w-3.5 mr-1" />
          Back to Projects
        </Button>
        <PageHeader title={project.name} description={project.description} />
      </div>

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

      <Tabs defaultValue="personas">
        <TabsList>
          <TabsTrigger value="personas">
            <Users className="h-3.5 w-3.5 mr-1.5 inline" />
            Personas
          </TabsTrigger>
          <TabsTrigger value="style-guide">
            <BookOpen className="h-3.5 w-3.5 mr-1.5 inline" />
            Style Guide
          </TabsTrigger>
          <TabsTrigger value="knowledge">
            <BookOpen className="h-3.5 w-3.5 mr-1.5 inline" />
            Knowledge
          </TabsTrigger>
          <TabsTrigger value="images">
            <Image className="h-3.5 w-3.5 mr-1.5 inline" />
            Images
          </TabsTrigger>
          <TabsTrigger value="settings">
            <Settings className="h-3.5 w-3.5 mr-1.5 inline" />
            Settings
          </TabsTrigger>
        </TabsList>

        {/* Personas Tab */}
        <TabsContent value="personas">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-sans text-heading-4 font-semibold text-cream-900">
                Project Personas ({project.personas.length})
              </h3>
              <div className="flex items-center gap-2">
                <ResearchTrigger
                  mode="persona"
                  companySlug={project.slug}
                  companyName={project.name}
                  domain={`${project.slug}.com`}
                  onStarted={(runId) => {
                    setResearchRun(runId, 'running', 'persona');
                  }}
                />
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setEditingPersona(undefined);
                    setPersonaEditorOpen(true);
                  }}
                >
                  <Plus className="h-3.5 w-3.5 mr-1" />
                  Add
                </Button>
              </div>
            </div>
            {project.personas.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center bg-white rounded-md border border-[var(--border-default)]">
                <Users className="h-10 w-10 text-cream-500 mb-3" />
                <p className="text-body-sm text-cream-600">
                  No personas for this project yet.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {project.personas.map((persona) => (
                  <PersonaCard
                    key={persona.id}
                    persona={persona}
                    onEdit={(p) => {
                      setEditingPersona(p);
                      setPersonaEditorOpen(true);
                    }}
                    onDelete={handlePersonaDelete}
                  />
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        {/* Style Guide Tab */}
        <TabsContent value="style-guide">
          <StyleGuideViewer
            content={project.style_guide ?? null}
            status={project.style_guide ? 'approved' : 'none'}
            onEdit={(newContent) => {
              updateProject({ style_guide: newContent });
              toast('Style guide updated', 'success');
            }}
            onGenerate={() => {
              // Trigger research for this project
            }}
          />
        </TabsContent>

        {/* Knowledge Tab */}
        <TabsContent value="knowledge">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-sans text-heading-4 font-semibold text-cream-900">
                Knowledge Documents ({project.knowledge_docs.length})
              </h3>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setEditingDoc(undefined);
                  setDocEditorOpen(true);
                }}
              >
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add Document
              </Button>
            </div>
            {project.knowledge_docs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center bg-white rounded-md border border-[var(--border-default)]">
                <BookOpen className="h-10 w-10 text-cream-500 mb-3" />
                <p className="text-body-sm text-cream-600">
                  No knowledge documents for this project yet.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {project.knowledge_docs.map((doc) => (
                  <KnowledgeDocCard
                    key={doc.id}
                    doc={doc}
                    onEdit={(d) => {
                      setEditingDoc(d);
                      setDocEditorOpen(true);
                    }}
                    onDelete={handleDocDelete}
                  />
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        {/* Images Tab (Placeholder) */}
        <TabsContent value="images">
          <div className="flex flex-col items-center justify-center py-16 text-center bg-white rounded-md border border-[var(--border-default)]">
            <Image className="h-12 w-12 text-cream-500 mb-4" />
            <h3 className="font-serif text-heading-3 text-cream-800 mb-2">
              Images & Assets
            </h3>
            <p className="text-body text-cream-600 max-w-md">
              Image upload and management will be available in a future update.
            </p>
          </div>
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings">
          <div className="max-w-lg space-y-6">
            <div className="bg-white rounded-md border border-[var(--border-default)] p-5 space-y-4">
              <h3 className="font-sans text-heading-4 font-semibold text-cream-900">
                Project Settings
              </h3>
              <Input
                label="Project Name"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
              />
              <div>
                <label className="block text-body-sm font-sans font-medium text-cream-800 mb-1.5">
                  Description
                </label>
                <textarea
                  value={projectDescription}
                  onChange={(e) => setProjectDescription(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 bg-white border border-[var(--border-default)] rounded-md font-body text-body text-cream-900 placeholder:text-cream-600 focus:outline-none focus:ring-2 focus:ring-terracotta-400/20 focus:border-terracotta-400 resize-none"
                />
              </div>
              <Button size="sm" onClick={handleSaveSettings}>
                Save Settings
              </Button>
            </div>

            <div className="bg-white rounded-md border border-error/30 p-5 space-y-3">
              <h3 className="font-sans text-heading-4 font-semibold text-error">
                Danger Zone
              </h3>
              <p className="text-body-sm text-cream-700">
                Permanently delete this project and all its data. This action cannot
                be undone.
              </p>
              <Button variant="danger" size="sm" onClick={handleDeleteProject}>
                <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                Delete Project
              </Button>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      <PersonaEditor
        open={personaEditorOpen}
        onClose={() => {
          setPersonaEditorOpen(false);
          setEditingPersona(undefined);
        }}
        persona={editingPersona}
        onSave={handlePersonaSave}
      />

      <KnowledgeDocEditor
        open={docEditorOpen}
        onClose={() => {
          setDocEditorOpen(false);
          setEditingDoc(undefined);
        }}
        doc={editingDoc}
        onSave={handleDocSave}
        projectId={projectId}
      />
    </div>
  );
}
