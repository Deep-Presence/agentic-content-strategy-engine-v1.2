'use client';

import { Building2, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ArtifactViewer } from './artifact-viewer';

interface CompanyContextSectionProps {
  content: string | null;
  status: 'none' | 'draft' | 'approved';
  companyName: string;
  onGenerate?: () => void;
  onEdit?: (newContent: string) => void;
}

export function CompanyContextSection({
  content,
  status,
  companyName,
  onGenerate,
  onEdit,
}: CompanyContextSectionProps) {
  if (!content) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center bg-white rounded-md border border-[var(--border-default)]">
        <Building2 className="h-12 w-12 text-cream-500 mb-4" />
        <h3 className="font-serif text-heading-3 text-cream-800 mb-2">
          No Company Context
        </h3>
        <p className="text-body text-cream-600 max-w-md mb-6">
          Generate a company context for {companyName} using the Research Pipeline.
          This gives AI agents deep understanding of the business.
        </p>
        {onGenerate && (
          <Button onClick={onGenerate}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Generate Company Context
          </Button>
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <Badge variant={status === 'approved' ? 'green' : 'warning'}>
          {status === 'approved' ? 'Approved' : 'Draft'}
        </Badge>
        {onGenerate && (
          <Button variant="secondary" size="sm" onClick={onGenerate}>
            <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
            Regenerate
          </Button>
        )}
      </div>
      <ArtifactViewer
        content={content}
        title={`${companyName} — Company Context`}
        type="company_context"
        editable={!!onEdit}
        onSave={onEdit}
      />
    </div>
  );
}
