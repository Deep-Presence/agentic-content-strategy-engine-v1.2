'use client';

import { Download } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { Button } from '@/components/ui/button';
import { CompanySelector } from './components/company-selector';
import { LabWorkspace } from './components/lab-workspace';

export default function EmbeddingLabPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Deep Embedding Lab"
        description="Explore citation patterns and content gaps through interactive visualizations"
        actions={
          <div className="flex items-center gap-3">
            <CompanySelector />
            <Button variant="secondary" size="sm">
              <Download className="h-3.5 w-3.5" />
              Export
            </Button>
          </div>
        }
      />
      <LabWorkspace />
    </div>
  );
}
