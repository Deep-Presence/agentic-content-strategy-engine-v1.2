"use client";

import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import React from "react";

interface MarkdownViewerProps {
  content: string;
  className?: string;
}

export const MarkdownViewer = React.memo(function MarkdownViewer({
  content,
  className,
}: MarkdownViewerProps) {
  return (
    <div className={className}>
      <ReactMarkdown
        rehypePlugins={[rehypeRaw, rehypeSanitize]}
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="font-display text-[1.75rem] text-ink mb-6 mt-0 leading-tight tracking-tight">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="font-display text-[1.375rem] text-ink mb-4 mt-8 leading-snug tracking-tight">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="font-body font-semibold text-[1.125rem] text-ink mb-3 mt-6">
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p className="font-body text-[1rem] text-ink leading-relaxed mb-4">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="ml-6 mb-4 space-y-1 list-disc marker:text-terracotta-300">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="ml-6 mb-4 space-y-1 list-decimal marker:text-terracotta-400">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="font-body text-[1rem] text-ink leading-relaxed">
              {children}
            </li>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              className="text-terracotta-600 hover:text-terracotta-700 underline underline-offset-2"
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-[3px] border-terracotta-300 pl-4 my-4 italic text-ink-secondary">
              {children}
            </blockquote>
          ),
          code: ({ className, children }) => {
            const isBlock = className?.includes("language-");
            if (isBlock) {
              return (
                <code className="block font-mono bg-[#2C2420] text-canvas p-4 rounded-lg overflow-x-auto text-[0.875rem] leading-relaxed">
                  {children}
                </code>
              );
            }
            return (
              <code className="font-mono bg-canvas-subtle px-1.5 py-0.5 rounded text-terracotta-700 text-[0.875rem]">
                {children}
              </code>
            );
          },
          pre: ({ children }) => (
            <pre className="my-4 overflow-hidden rounded-lg">{children}</pre>
          ),
          table: ({ children }) => (
            <div className="my-4 overflow-x-auto rounded-lg border border-canvas-muted">
              <table className="w-full text-[0.875rem]">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-canvas-subtle border-b border-canvas-muted">
              {children}
            </thead>
          ),
          th: ({ children }) => (
            <th className="px-4 py-2.5 text-left font-body font-semibold text-ink text-[0.8125rem]">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-4 py-2.5 text-ink border-t border-canvas-muted">
              {children}
            </td>
          ),
          hr: () => <hr className="border-canvas-muted my-8" />,
          strong: ({ children }) => (
            <strong className="font-semibold text-ink">{children}</strong>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
});
