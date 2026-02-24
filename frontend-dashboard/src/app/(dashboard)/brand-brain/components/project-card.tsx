'use client';

import Link from 'next/link';
import { FolderOpen, CheckCircle, XCircle, ArrowRight } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { relativeTime } from '@/lib/utils/format';
import type { Project } from '@/types/brand';

interface ProjectCardProps {
  project: Project;
}

export function ProjectCard({ project }: ProjectCardProps) {
  const personaCount = project.personas.length;
  const hasStyleGuide = !!project.style_guide;
  const docCount = project.knowledge_docs.length;

  return (
    <Link href={`/brand-brain/projects/${project.id}`}>
      <Card hoverable accent="terracotta" className="h-full">
        <CardHeader>
          <div className="flex items-center gap-2">
            <FolderOpen className="h-4 w-4 text-terracotta-400" />
            <CardTitle>{project.name}</CardTitle>
          </div>
          {project.description && (
            <CardDescription>{project.description}</CardDescription>
          )}
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 text-body-sm font-sans text-cream-700">
            <span>
              Personas: <span className="font-medium text-cream-900">{personaCount}</span>
            </span>
            <span className="flex items-center gap-1">
              Style Guide:{' '}
              {hasStyleGuide ? (
                <CheckCircle className="h-3.5 w-3.5 text-sage-400" />
              ) : (
                <XCircle className="h-3.5 w-3.5 text-cream-500" />
              )}
            </span>
          </div>
          <div className="mt-2 text-body-sm font-sans text-cream-700">
            Knowledge Docs: <span className="font-medium text-cream-900">{docCount}</span>
          </div>
        </CardContent>
        <CardFooter>
          <div className="flex items-center justify-between w-full">
            <span className="text-caption font-sans text-cream-600">
              Created {relativeTime(project.created_at)}
            </span>
            <Badge variant="terracotta" className="flex items-center gap-1">
              Open <ArrowRight className="h-3 w-3" />
            </Badge>
          </div>
        </CardFooter>
      </Card>
    </Link>
  );
}
