'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useMemo } from 'react';
import type { Components } from 'react-markdown';

interface MarkdownRendererProps {
  content: string;
  onHeadingsReady?: (headings: { id: string; text: string; level: number }[]) => void;
}

function generateId(text: string): string {
  return text.toLowerCase().replace(/\s+/g, '-').replace(/[^\w-]/g, '');
}

const markdownComponents: Components = {
  h1: ({ children }) => {
    const text = String(children);
    return (
      <h1 id={generateId(text)} className="font-display text-[28px] font-semibold tracking-[-0.02em] text-text-primary mb-4">
        {children}
      </h1>
    );
  },
  h2: ({ children }) => {
    const text = String(children);
    return (
      <h2 id={generateId(text)} className="font-display text-[18px] font-semibold tracking-[-0.02em] text-text-primary mt-6 mb-3 pt-6 border-t border-border">
        {children}
      </h2>
    );
  },
  h3: ({ children }) => {
    const text = String(children);
    return (
      <h3 id={generateId(text)} className="font-display text-[15px] font-semibold tracking-[-0.01em] text-text-primary mt-4 mb-2">
        {children}
      </h3>
    );
  },
  p: ({ children }) => (
    <p className="text-[14px] text-text-secondary leading-[1.6] mb-3">{children}</p>
  ),
  a: ({ href, children }) => (
    <a href={href} className="text-accent hover:underline" target="_blank" rel="noopener noreferrer">{children}</a>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-4">
      <table className="w-full border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead>{children}</thead>,
  tbody: ({ children }) => <tbody>{children}</tbody>,
  tr: ({ children }) => <tr>{children}</tr>,
  th: ({ children }) => (
    <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-left p-[6px_10px] border-b border-border">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="text-[12px] p-[6px_10px] border-b border-border-subtle">{children}</td>
  ),
  code: ({ children, className }) => {
    const isBlock = className?.includes('language-');
    if (isBlock) {
      return (
        <code className="block font-mono text-[12px] bg-bg border border-border rounded-md p-3 overflow-x-auto my-3 whitespace-pre">
          {children}
        </code>
      );
    }
    return (
      <code className="font-mono text-[12px] bg-surface border border-border rounded-sm px-1">
        {children}
      </code>
    );
  },
  pre: ({ children }) => <pre className="my-3">{children}</pre>,
  ul: ({ children }) => <ul className="space-y-1 mb-3 pl-4">{children}</ul>,
  ol: ({ children }) => <ol className="space-y-1 mb-3 pl-4 list-decimal">{children}</ol>,
  li: ({ children }) => (
    <li className="text-[14px] text-text-secondary leading-[1.55] list-disc">{children}</li>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-accent pl-3 my-3 text-[13px] text-text-secondary italic">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="border-border my-6" />,
  strong: ({ children }) => <strong className="font-semibold text-text-primary">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
};

export function MarkdownRenderer({ content, onHeadingsReady }: MarkdownRendererProps) {
  useMemo(() => {
    if (onHeadingsReady) {
      const headings: { id: string; text: string; level: number }[] = [];
      const lines = content.split('\n');
      for (const line of lines) {
        const match = line.match(/^(#{1,3})\s+(.+)/);
        if (match) {
          const level = match[1].length;
          const text = match[2].replace(/\*\*/g, '').trim();
          headings.push({ id: generateId(text), text, level });
        }
      }
      onHeadingsReady(headings);
    }
  }, [content, onHeadingsReady]);

  return (
    <div className="max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
