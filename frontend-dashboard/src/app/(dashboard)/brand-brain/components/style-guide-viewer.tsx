'use client';

import { BookOpen, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ArtifactViewer } from './artifact-viewer';

interface StyleGuideViewerProps {
  content: string | null;
  status: 'none' | 'draft' | 'approved';
  onEdit?: (newContent: string) => void;
  onGenerate?: () => void;
}

export function StyleGuideViewer({
  content,
  status,
  onEdit,
  onGenerate,
}: StyleGuideViewerProps) {
  if (!content) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center bg-white rounded-md border border-[var(--border-default)]">
        <BookOpen className="h-12 w-12 text-cream-500 mb-4" />
        <h3 className="font-serif text-heading-3 text-cream-800 mb-2">
          No Style Guide Yet
        </h3>
        <p className="text-body text-cream-600 max-w-md mb-6">
          Generate a writing style guide using the Research Pipeline, or create one manually.
        </p>
        {onGenerate && (
          <Button onClick={onGenerate}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Generate Style Guide
          </Button>
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Badge variant={status === 'approved' ? 'green' : 'warning'}>
            {status === 'approved' ? 'Approved' : 'Draft'}
          </Badge>
        </div>
        {onGenerate && (
          <Button variant="secondary" size="sm" onClick={onGenerate}>
            <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
            Regenerate
          </Button>
        )}
      </div>
      <ArtifactViewer
        content={content}
        title="Style Guide"
        type="style_guide"
        editable={!!onEdit}
        onSave={onEdit}
      />
    </div>
  );
}
