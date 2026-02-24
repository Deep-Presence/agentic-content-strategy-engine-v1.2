'use client';

import { useState } from 'react';
import { Plus, FolderOpen } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { Button } from '@/components/ui/button';
import { useBrandStore } from '@/stores/brand-store';
import { ProjectCard } from '../components/project-card';
import { CreateProjectDialog } from '../components/create-project-dialog';

export default function ProjectsPage() {
  const projects = useBrandStore((s) => s.projects);
  const [showCreate, setShowCreate] = useState(false);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Projects"
        description="Product-level knowledge bases"
        actions={
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4 mr-1.5" />
            New Project
          </Button>
        }
      />

      {projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center bg-white rounded-md border border-[var(--border-default)]">
          <FolderOpen className="h-12 w-12 text-cream-500 mb-4" />
          <h3 className="font-serif text-heading-3 text-cream-800 mb-2">
            No Projects Yet
          </h3>
          <p className="text-body text-cream-600 max-w-md mb-6">
            Create a project to build a product-specific knowledge base with its own
            personas, style guide, and documentation.
          </p>
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4 mr-1.5" />
            Create First Project
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}

      <CreateProjectDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
      />
    </div>
  );
}
