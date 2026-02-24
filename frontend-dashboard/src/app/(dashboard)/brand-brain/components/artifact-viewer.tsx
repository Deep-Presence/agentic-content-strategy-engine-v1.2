'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { Pencil, Save, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';

interface ArtifactViewerProps {
  content: string;
  title: string;
  type: 'company_context' | 'persona' | 'style_guide';
  editable?: boolean;
  onSave?: (newContent: string) => void;
  className?: string;
}

export function ArtifactViewer({
  content,
  title,
  type,
  editable = false,
  onSave,
  className,
}: ArtifactViewerProps) {
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState(content);

  const handleSave = () => {
    onSave?.(editContent);
    setEditing(false);
  };

  const handleCancel = () => {
    setEditContent(content);
    setEditing(false);
  };

  const typeLabel = {
    company_context: 'Company Context',
    persona: 'Persona',
    style_guide: 'Style Guide',
  }[type];

  return (
    <div
      className={cn(
        'bg-white rounded-md border border-[var(--border-default)]',
        className
      )}
    >
      <div className="flex items-center justify-between p-4 border-b border-[var(--border-subtle)]">
        <div>
          <h3 className="font-serif text-heading-3 text-cream-950">{title}</h3>
          <span className="text-caption font-sans text-cream-600">{typeLabel}</span>
        </div>
        {editable && !editing && (
          <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
            <Pencil className="h-3.5 w-3.5 mr-1.5" />
            Edit
          </Button>
        )}
        {editing && (
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={handleCancel}>
              <X className="h-3.5 w-3.5 mr-1.5" />
              Cancel
            </Button>
            <Button size="sm" onClick={handleSave}>
              <Save className="h-3.5 w-3.5 mr-1.5" />
              Save
            </Button>
          </div>
        )}
      </div>
      <div className="p-5">
        {editing ? (
          <textarea
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            className="w-full min-h-[400px] p-4 bg-cream-100 border border-[var(--border-default)] rounded-md font-body text-body text-cream-900 focus:outline-none focus:ring-2 focus:ring-terracotta-400/20 focus:border-terracotta-400 resize-y"
          />
        ) : (
          <div className="prose-brand max-w-none">
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
                  <h2 className="font-serif text-heading-2 font-semibold text-cream-950 mt-5 mb-2">
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 className="font-serif text-heading-3 font-semibold text-cream-900 mt-4 mb-2">
                    {children}
                  </h3>
                ),
                h4: ({ children }) => (
                  <h4 className="font-serif text-heading-4 font-semibold text-cream-900 mt-3 mb-1">
                    {children}
                  </h4>
                ),
                p: ({ children }) => (
                  <p className="font-body text-body text-cream-800 mb-3 leading-relaxed">
                    {children}
                  </p>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc list-inside font-body text-body text-cream-800 mb-3 space-y-1 ml-2">
                    {children}
                  </ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal list-inside font-body text-body text-cream-800 mb-3 space-y-1 ml-2">
                    {children}
                  </ol>
                ),
                li: ({ children }) => (
                  <li className="font-body text-body text-cream-800">{children}</li>
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
                table: ({ children }) => (
                  <div className="overflow-x-auto my-3">
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
                hr: () => (
                  <hr className="my-6 border-[var(--border-default)]" />
                ),
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
