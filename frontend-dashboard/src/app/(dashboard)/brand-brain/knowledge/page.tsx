'use client';

import { useState } from 'react';
import { Plus, BookOpen } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { Button } from '@/components/ui/button';
import { useAppStore } from '@/stores/app-store';
import { useBrandStore } from '@/stores/brand-store';
import { useToast } from '@/components/ui/toast';
import { KnowledgeDocCard } from '../components/knowledge-doc-card';
import { KnowledgeDocEditor } from '../components/knowledge-doc-editor';
import type { KnowledgeDoc } from '@/types/brand';

export default function KnowledgePage() {
  const { toast } = useToast();
  const currentCompany = useAppStore((s) => s.currentCompany);
  const {
    knowledgeDocs,
    addKnowledgeDoc,
    updateKnowledgeDoc,
    removeKnowledgeDoc,
    setKnowledgeDocs,
  } = useBrandStore();

  const [editorOpen, setEditorOpen] = useState(false);
  const [editingDoc, setEditingDoc] = useState<KnowledgeDoc | undefined>();

  const companyName = currentCompany
    ? currentCompany.charAt(0).toUpperCase() + currentCompany.slice(1)
    : '';

  const handleEdit = (doc: KnowledgeDoc) => {
    setEditingDoc(doc);
    setEditorOpen(true);
  };

  const handleDelete = (id: string) => {
    removeKnowledgeDoc(id);
    toast('Document removed', 'info');
  };

  const handleSave = (doc: KnowledgeDoc) => {
    if (editingDoc) {
      updateKnowledgeDoc(doc.id, doc);
    } else {
      addKnowledgeDoc(doc);
    }
    setEditingDoc(undefined);
  };

  const handleCreateNew = () => {
    setEditingDoc(undefined);
    setEditorOpen(true);
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="Knowledge Base"
        description={`Global knowledge documents for ${companyName}`}
        actions={
          <Button size="sm" onClick={handleCreateNew}>
            <Plus className="h-4 w-4 mr-1.5" />
            Add Document
          </Button>
        }
      />

      {knowledgeDocs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center bg-white rounded-md border border-[var(--border-default)]">
          <BookOpen className="h-12 w-12 text-cream-500 mb-4" />
          <h3 className="font-serif text-heading-3 text-cream-800 mb-2">
            No Knowledge Documents Yet
          </h3>
          <p className="text-body text-cream-600 max-w-md mb-6">
            Add brand guidelines, product context, voice & tone guides, or other
            documents to give your AI agents deeper understanding.
          </p>
          <Button onClick={handleCreateNew}>
            <Plus className="h-4 w-4 mr-1.5" />
            Add Document
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {knowledgeDocs.map((doc) => (
            <KnowledgeDocCard
              key={doc.id}
              doc={doc}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      <KnowledgeDocEditor
        open={editorOpen}
        onClose={() => {
          setEditorOpen(false);
          setEditingDoc(undefined);
        }}
        doc={editingDoc}
        onSave={handleSave}
      />
    </div>
  );
}
