'use client';

import { FileText, Pencil, Trash2 } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { KnowledgeDoc } from '@/types/brand';

interface KnowledgeDocCardProps {
  doc: KnowledgeDoc;
  onEdit?: (doc: KnowledgeDoc) => void;
  onDelete?: (id: string) => void;
}

const TYPE_LABELS: Record<KnowledgeDoc['type'], string> = {
  brand_guidelines: 'Brand Guidelines',
  product_context: 'Product Context',
  voice_recording: 'Voice & Tone',
  style_guide: 'Style Guide',
  images: 'Images',
  other: 'Other',
};

const TYPE_VARIANTS: Record<KnowledgeDoc['type'], 'terracotta' | 'blue' | 'green' | 'default'> = {
  brand_guidelines: 'terracotta',
  product_context: 'blue',
  voice_recording: 'green',
  style_guide: 'blue',
  images: 'default',
  other: 'default',
};

export function KnowledgeDocCard({ doc, onEdit, onDelete }: KnowledgeDocCardProps) {
  const preview = doc.content.slice(0, 150).replace(/\n/g, ' ');

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-start gap-2">
          <FileText className="h-4 w-4 text-terracotta-400 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <CardTitle className="truncate">{doc.title}</CardTitle>
            <div className="mt-1">
              <Badge variant={TYPE_VARIANTS[doc.type]}>
                {TYPE_LABELS[doc.type]}
              </Badge>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <p className="font-body text-body-sm text-cream-700 line-clamp-3">
          &ldquo;{preview}{doc.content.length > 150 ? '...' : ''}&rdquo;
        </p>
      </CardContent>
      <CardFooter>
        <div className="flex items-center gap-2">
          {onEdit && (
            <Button variant="ghost" size="sm" onClick={() => onEdit(doc)}>
              <Pencil className="h-3.5 w-3.5 mr-1" />
              Edit
            </Button>
          )}
          {onDelete && (
            <Button variant="ghost" size="sm" onClick={() => onDelete(doc.id)}>
              <Trash2 className="h-3.5 w-3.5 mr-1" />
              Delete
            </Button>
          )}
        </div>
      </CardFooter>
    </Card>
  );
}
