'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { BookOpen, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

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

      {/* Beautiful reading view */}
      <div className="bg-white rounded-md border border-[var(--border-default)] shadow-[var(--shadow-sm)]">
        <div className="border-b border-[var(--border-subtle)] px-8 py-5">
          <div className="flex items-center gap-3">
            <BookOpen className="h-5 w-5 text-terracotta-400" />
            <h2 className="font-serif text-heading-2 font-semibold text-cream-950">
              Style Guide
            </h2>
          </div>
          <p className="font-sans text-caption text-cream-600 mt-1 ml-8">
            Writing guidelines and content standards
          </p>
        </div>

        <div className="px-8 py-6 md:px-12 md:py-8 lg:px-16">
          <div className="max-w-3xl mx-auto">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeSanitize]}
              components={{
                h1: ({ children }) => (
                  <h1 className="font-serif text-[1.75rem] leading-tight font-semibold text-cream-950 mt-10 mb-4 first:mt-0 pb-2 border-b border-[var(--border-subtle)]">
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className="font-serif text-heading-2 font-semibold text-cream-950 mt-8 mb-3">
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 className="font-serif text-heading-3 font-semibold text-cream-900 mt-6 mb-2">
                    {children}
                  </h3>
                ),
                h4: ({ children }) => (
                  <h4 className="font-serif text-heading-4 font-semibold text-cream-900 mt-4 mb-1.5">
                    {children}
                  </h4>
                ),
                p: ({ children }) => (
                  <p className="font-body text-body text-cream-800 mb-4 leading-[1.75]">
                    {children}
                  </p>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc font-body text-body text-cream-800 mb-4 space-y-2 pl-5">
                    {children}
                  </ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal font-body text-body text-cream-800 mb-4 space-y-2 pl-5">
                    {children}
                  </ol>
                ),
                li: ({ children }) => (
                  <li className="font-body text-body text-cream-800 leading-[1.7]">
                    {children}
                  </li>
                ),
                strong: ({ children }) => (
                  <strong className="font-semibold text-cream-950">{children}</strong>
                ),
                em: ({ children }) => (
                  <em className="italic text-cream-700">{children}</em>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="border-l-3 border-terracotta-400 pl-5 py-2 my-4 bg-terracotta-50/30 rounded-r-md pr-4">
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
                    <code className="block font-mono text-body-sm bg-cream-100 p-4 rounded-md my-4 overflow-x-auto text-cream-800 border border-[var(--border-subtle)]">
                      {children}
                    </code>
                  );
                },
                hr: () => (
                  <hr className="my-8 border-[var(--border-default)]" />
                ),
                table: ({ children }) => (
                  <div className="overflow-x-auto my-5 rounded-md border border-[var(--border-default)]">
                    <table className="w-full border-collapse text-body-sm font-sans">
                      {children}
                    </table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead className="bg-cream-100">{children}</thead>
                ),
                th: ({ children }) => (
                  <th className="text-cream-800 font-semibold text-left px-4 py-2.5 border-b border-[var(--border-default)]">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="px-4 py-2.5 border-b border-[var(--border-subtle)] text-cream-800">
                    {children}
                  </td>
                ),
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
}
