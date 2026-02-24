'use client';

import { useState } from 'react';
import { User, Target, Eye, Pencil, Trash2 } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';
import { ArtifactViewer } from './artifact-viewer';
import type { Persona } from '@/types/brand';

interface PersonaCardProps {
  persona: Persona;
  onEdit?: (persona: Persona) => void;
  onDelete?: (id: string) => void;
  source?: string;
  status?: 'approved' | 'draft';
}

export function PersonaCard({
  persona,
  onEdit,
  onDelete,
  source = 'Manual',
  status = 'approved',
}: PersonaCardProps) {
  const [expanded, setExpanded] = useState(false);

  const preview = persona.content.slice(0, 200).replace(/\n/g, ' ');
  const Icon = persona.type === 'icp' ? Target : User;

  return (
    <>
      <Card accent="terracotta" className="h-full">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Icon className="h-4 w-4 text-terracotta-400" />
            <CardTitle className="flex-1">
              {persona.type === 'icp' ? 'ICP' : 'Secondary'} — {persona.name}
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <p className="font-body text-body-sm text-cream-700 line-clamp-4">
            &ldquo;{preview}{persona.content.length > 200 ? '...' : ''}&rdquo;
          </p>
          <div className="mt-3 flex items-center gap-3">
            <span className="text-caption font-sans text-cream-600">
              Source: {source}
            </span>
            <Badge variant={status === 'approved' ? 'green' : 'warning'}>
              {status === 'approved' ? 'Approved' : 'Draft'}
            </Badge>
          </div>
        </CardContent>
        <CardFooter>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setExpanded(true)}>
              <Eye className="h-3.5 w-3.5 mr-1" />
              View Full
            </Button>
            {onEdit && (
              <Button variant="ghost" size="sm" onClick={() => onEdit(persona)}>
                <Pencil className="h-3.5 w-3.5 mr-1" />
                Edit
              </Button>
            )}
            {onDelete && (
              <Button variant="ghost" size="sm" onClick={() => onDelete(persona.id)}>
                <Trash2 className="h-3.5 w-3.5 mr-1" />
                Delete
              </Button>
            )}
          </div>
        </CardFooter>
      </Card>

      {expanded && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="fixed inset-0 bg-cream-950/40"
            onClick={() => setExpanded(false)}
          />
          <div className="relative z-10 w-full max-w-3xl max-h-[80vh] overflow-y-auto bg-[var(--bg-primary)] rounded-lg shadow-xl border border-[var(--border-default)]">
            <div className="sticky top-0 bg-[var(--bg-primary)] border-b border-[var(--border-default)] p-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Icon className={cn('h-5 w-5 text-terracotta-400')} />
                <h2 className="font-serif text-heading-2 text-cream-950">
                  {persona.name}
                </h2>
                <Badge variant={persona.type === 'icp' ? 'terracotta' : 'default'}>
                  {persona.type === 'icp' ? 'ICP' : 'Secondary'}
                </Badge>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setExpanded(false)}>
                Close
              </Button>
            </div>
            <div className="p-1">
              <ArtifactViewer
                content={persona.content}
                title={persona.name}
                type="persona"
                className="border-0 shadow-none"
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
