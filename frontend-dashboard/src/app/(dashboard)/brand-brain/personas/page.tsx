'use client';

import { useState, useEffect, useCallback } from 'react';
import { Users, Plus } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { useAppStore } from '@/stores/app-store';
import { useBrandStore } from '@/stores/brand-store';
import { artifacts } from '@/lib/api/artifacts';
import { PersonaCard } from '../components/persona-card';
import { PersonaEditor } from '../components/persona-editor';
import { ResearchTrigger } from '../components/research-trigger';
import { ResearchProgress } from '../components/research-progress';
import { ResearchApprovalInline } from '../components/research-approval-inline';
import { MOCK_PERSONA_ICP, MOCK_PERSONA_SECONDARY } from '../data/mock-artifacts';
import type { Persona } from '@/types/brand';

export default function PersonasPage() {
  const { toast } = useToast();
  const currentCompany = useAppStore((s) => s.currentCompany);
  const {
    personas,
    setPersonas,
    addPersona,
    removePersona,
    activeResearchRunId,
    approvalPayload,
    setResearchRun,
  } = useBrandStore();

  const [loading, setLoading] = useState(true);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingPersona, setEditingPersona] = useState<Persona | undefined>();
  const [approvalStage, setApprovalStage] = useState<string | null>(null);
  const [approvalContent, setApprovalContent] = useState('');

  const companyName = currentCompany
    ? currentCompany.charAt(0).toUpperCase() + currentCompany.slice(1)
    : 'Webflow';

  const loadPersonas = useCallback(async () => {
    // If already loaded in store, skip
    if (personas.length > 0) {
      setLoading(false);
      return;
    }

    setLoading(true);
    let loaded = false;

    if (currentCompany) {
      try {
        const personaFiles = await artifacts.listFiles('personas', currentCompany);
        const loadedPersonas: Persona[] = [];

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
                name: file
                  .replace(`${currentCompany}__`, '')
                  .replace('.md', '')
                  .replace(/-/g, ' '),
                type: file.includes('icp') ? 'icp' : 'secondary',
                content: typeof content === 'string' ? content : JSON.stringify(content),
              });
            }
          } catch {
            // Skip failed files
          }
        }
        if (loadedPersonas.length > 0) {
          setPersonas(loadedPersonas);
          loaded = true;
        }
      } catch {
        // Fall through to mock
      }
    }

    if (!loaded) {
      setPersonas([
        {
          id: 'mock-icp-finance',
          name: 'Finance Director at Mid-Market B2B SaaS',
          type: 'icp',
          content: MOCK_PERSONA_ICP,
        },
        {
          id: 'mock-secondary-markops',
          name: 'Marketing Operations Manager',
          type: 'secondary',
          content: MOCK_PERSONA_SECONDARY,
        },
      ]);
    }

    setLoading(false);
  }, [currentCompany, personas.length, setPersonas]);

  useEffect(() => {
    loadPersonas();
  }, [loadPersonas]);

  const handleEdit = (persona: Persona) => {
    setEditingPersona(persona);
    setEditorOpen(true);
  };

  const handleDelete = (id: string) => {
    removePersona(id);
    toast('Persona removed', 'info');
  };

  const handleSave = (persona: Persona) => {
    if (editingPersona) {
      setPersonas(personas.map((p) => (p.id === persona.id ? persona : p)));
    } else {
      addPersona(persona);
    }
    setEditingPersona(undefined);
  };

  const handleCreateNew = () => {
    setEditingPersona(undefined);
    setEditorOpen(true);
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="Personas"
        description={`Audience personas for ${companyName}`}
        actions={
          <div className="flex items-center gap-2">
            <ResearchTrigger
              mode="persona"
              companySlug={currentCompany}
              companyName={companyName}
              domain={`${currentCompany ?? 'webflow'}.com`}
              onStarted={(runId) => {
                setResearchRun(runId, 'running', 'persona');
              }}
            />
            <Button variant="secondary" size="sm" onClick={handleCreateNew}>
              <Plus className="h-4 w-4 mr-1.5" />
              Manual Create
            </Button>
          </div>
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
              loadPersonas();
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

      {/* Personas Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2].map((i) => (
            <Skeleton key={i} className="h-64 rounded-md" />
          ))}
        </div>
      ) : personas.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center bg-white rounded-md border border-[var(--border-default)]">
          <Users className="h-12 w-12 text-cream-500 mb-4" />
          <h3 className="font-serif text-heading-3 text-cream-800 mb-2">
            No Personas Yet
          </h3>
          <p className="text-body text-cream-600 max-w-md mb-6">
            Generate personas using the Research Pipeline or create them manually.
          </p>
          <div className="flex items-center gap-3">
            <ResearchTrigger
              mode="persona"
              companySlug={currentCompany}
              companyName={companyName}
              domain={`${currentCompany ?? 'webflow'}.com`}
              onStarted={(runId) => {
                setResearchRun(runId, 'running', 'persona');
              }}
            />
            <Button variant="secondary" onClick={handleCreateNew}>
              <Plus className="h-4 w-4 mr-1.5" />
              Manual Create
            </Button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {personas.map((persona) => (
            <PersonaCard
              key={persona.id}
              persona={persona}
              onEdit={handleEdit}
              onDelete={handleDelete}
              source="Research Pipeline"
              status="approved"
            />
          ))}
        </div>
      )}

      <PersonaEditor
        open={editorOpen}
        onClose={() => {
          setEditorOpen(false);
          setEditingPersona(undefined);
        }}
        persona={editingPersona}
        onSave={handleSave}
      />
    </div>
  );
}
