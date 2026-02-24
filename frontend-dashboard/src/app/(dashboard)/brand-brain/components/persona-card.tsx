'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { User, Target, Eye, Pencil, Trash2 } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';
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
            <div className="sticky top-0 bg-[var(--bg-primary)] border-b border-[var(--border-default)] p-4 flex items-center justify-between z-10">
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
            <div className="p-6 md:p-8">
              <div className="max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeSanitize]}
                  components={{
                    h1: ({ children }) => (
                      <h1 className="font-serif text-heading-1 font-semibold text-cream-950 mt-6 mb-3 first:mt-0">
                        {children}
                      </h1>
                    ),
                    h2: ({ children }) => (
                      <h2 className="font-serif text-heading-2 font-semibold text-cream-950 mt-6 mb-3 first:mt-0">
                        {children}
                      </h2>
                    ),
                    h3: ({ children }) => (
                      <h3 className="font-serif text-heading-3 font-semibold text-cream-900 mt-5 mb-2">
                        {children}
                      </h3>
                    ),
                    h4: ({ children }) => (
                      <h4 className="font-serif text-heading-4 font-semibold text-cream-900 mt-4 mb-1.5">
                        {children}
                      </h4>
                    ),
                    p: ({ children }) => (
                      <p className="font-body text-body text-cream-800 mb-3 leading-relaxed">
                        {children}
                      </p>
                    ),
                    ul: ({ children }) => (
                      <ul className="list-disc font-body text-body text-cream-800 mb-3 space-y-1.5 pl-5">
                        {children}
                      </ul>
                    ),
                    ol: ({ children }) => (
                      <ol className="list-decimal font-body text-body text-cream-800 mb-3 space-y-1.5 pl-5">
                        {children}
                      </ol>
                    ),
                    li: ({ children }) => (
                      <li className="font-body text-body text-cream-800 leading-relaxed">
                        {children}
                      </li>
                    ),
                    strong: ({ children }) => (
                      <strong className="font-semibold text-cream-950">{children}</strong>
                    ),
                    em: ({ children }) => (
                      <em className="italic">{children}</em>
                    ),
                    blockquote: ({ children }) => (
                      <blockquote className="border-l-3 border-terracotta-400 pl-4 py-1 my-3 text-cream-700 italic">
                        {children}
                      </blockquote>
                    ),
                    code: ({ children, className: codeClassName }) => {
                      const isInline = !codeClassName;
                      if (isInline) {
                        return (
                          <code className="font-mono text-body-sm bg-cream-200 px-1.5 py-0.5 rounded text-terracotta-500">
                            {children}
                          </code>
                        );
                      }
                      return (
                        <code className="block font-mono text-body-sm bg-cream-100 p-4 rounded-md my-3 overflow-x-auto text-cream-800">
                          {children}
                        </code>
                      );
                    },
                    hr: () => (
                      <hr className="my-6 border-[var(--border-default)]" />
                    ),
                    table: ({ children }) => (
                      <div className="overflow-x-auto my-4">
                        <table className="w-full border-collapse text-body-sm font-sans">
                          {children}
                        </table>
                      </div>
                    ),
                    th: ({ children }) => (
                      <th className="bg-cream-200 text-cream-800 font-semibold text-left px-3 py-2 border border-[var(--border-default)]">
                        {children}
                      </th>
                    ),
                    td: ({ children }) => (
                      <td className="px-3 py-2 border border-[var(--border-subtle)] text-cream-800">
                        {children}
                      </td>
                    ),
                  }}
                >
                  {persona.content}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
