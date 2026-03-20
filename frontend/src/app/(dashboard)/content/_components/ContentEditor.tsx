'use client';

import { cn } from '@/lib/utils';
import { useState, useRef, useCallback, useEffect } from 'react';
import {
  Sparkles, RefreshCw, Minus, Plus, Palette,
  Bold, Italic, Link, Heading2, Heading3, Quote,
} from 'lucide-react';

interface ContentEditorProps {
  content: string;
  onChange: (content: string) => void;
  onToastMessage?: (message: string) => void;
}

interface ToolbarPosition {
  x: number;
  y: number;
}

export function ContentEditor({ content, onChange, onToastMessage }: ContentEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<HTMLDivElement>(null);
  const [showToolbar, setShowToolbar] = useState(false);
  const [toolbarPosition, setToolbarPosition] = useState<ToolbarPosition>({ x: 0, y: 0 });
  const contentLoadedRef = useRef(false);

  const handleAIAction = useCallback(
    (action: string) => {
      onToastMessage?.(`Coming soon — AI ${action}`);
      setShowToolbar(false);
    },
    [onToastMessage]
  );

  const handleFormat = useCallback((command: string, value?: string) => {
    document.execCommand(command, false, value);
    setShowToolbar(false);
  }, []);

  const handleSelection = useCallback(() => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || !selection.rangeCount) {
      setShowToolbar(false);
      return;
    }

    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    const containerRect = containerRef.current?.getBoundingClientRect();
    if (!containerRect) return;

    setToolbarPosition({
      x: rect.left - containerRect.left + rect.width / 2,
      y: rect.top - containerRect.top - 8,
    });
    setShowToolbar(true);
  }, []);

  const handleInput = useCallback(() => {
    if (editorRef.current) {
      onChange(editorRef.current.innerHTML);
    }
  }, [onChange]);

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    e.preventDefault();
    const text = e.clipboardData.getData('text/plain');
    document.execCommand('insertText', false, text);
  }, []);

  // Load markdown content into the contentEditable div
  useEffect(() => {
    if (editorRef.current && content) {
      // Only set innerHTML when content changes from parent (not from user edits)
      if (!contentLoadedRef.current || editorRef.current.innerHTML === '') {
        editorRef.current.innerHTML = markdownToHtml(content);
        contentLoadedRef.current = true;
      }
    }
  }, [content]);

  return (
    <div className="relative flex-1 overflow-y-auto" ref={containerRef}>
      {/* Floating Toolbar */}
      {showToolbar && (
        <div
          className="absolute z-50 bg-surface-raised border border-border rounded-md shadow-float p-1 flex flex-col gap-0.5"
          style={{
            top: toolbarPosition.y,
            left: toolbarPosition.x,
            transform: 'translate(-50%, -100%)',
          }}
        >
          {/* AI Actions Row */}
          <div className="flex gap-0.5 border-b border-border pb-1 mb-0.5">
            <ToolbarButton icon={<Sparkles size={11} />} label="Regenerate" onClick={() => handleAIAction('regeneration')} />
            <ToolbarButton icon={<RefreshCw size={11} />} label="Rewrite" onClick={() => handleAIAction('rewrite')} />
            <ToolbarButton icon={<Minus size={11} />} label="Shorten" onClick={() => handleAIAction('shorten')} />
            <ToolbarButton icon={<Plus size={11} />} label="Expand" onClick={() => handleAIAction('expand')} />
            <ToolbarButton icon={<Palette size={11} />} label="Tone" onClick={() => handleAIAction('tone change')} />
          </div>
          {/* Format Row */}
          <div className="flex gap-0.5">
            <ToolbarButton icon={<Bold size={11} />} label="Bold" onClick={() => handleFormat('bold')} />
            <ToolbarButton icon={<Italic size={11} />} label="Italic" onClick={() => handleFormat('italic')} />
            <ToolbarButton icon={<Link size={11} />} label="Link" onClick={() => handleFormat('createLink', '#')} />
            <ToolbarButton icon={<Heading2 size={11} />} label="H2" onClick={() => handleFormat('formatBlock', 'h2')} />
            <ToolbarButton icon={<Heading3 size={11} />} label="H3" onClick={() => handleFormat('formatBlock', 'h3')} />
            <ToolbarButton icon={<Quote size={11} />} label="Quote" onClick={() => handleFormat('formatBlock', 'blockquote')} />
          </div>
        </div>
      )}

      {/* Editor Surface */}
      <div
        ref={editorRef}
        className={cn(
          'min-h-full p-6 font-body text-[14px] leading-[1.6] text-text-primary',
          'outline-none max-w-[700px] mx-auto',
          '[&_h1]:text-[20px] [&_h1]:font-semibold [&_h1]:mb-3 [&_h1]:mt-6 [&_h1]:text-text-primary [&_h1]:leading-[1.2] [&_h1]:tracking-[-0.02em]',
          '[&_h2]:text-[16px] [&_h2]:font-semibold [&_h2]:mb-2 [&_h2]:mt-5 [&_h2]:text-text-primary [&_h2]:leading-[1.25] [&_h2]:tracking-[-0.01em]',
          '[&_h3]:text-[14px] [&_h3]:font-semibold [&_h3]:mb-2 [&_h3]:mt-4 [&_h3]:text-text-primary [&_h3]:leading-[1.3]',
          '[&_h4]:text-[13px] [&_h4]:font-semibold [&_h4]:mb-1 [&_h4]:mt-3 [&_h4]:text-text-primary',
          '[&_p]:mb-3 [&_p]:text-text-secondary',
          '[&_ul]:mb-3 [&_ul]:pl-5 [&_ul]:list-disc [&_ul_li]:mb-1 [&_ul_li]:text-text-secondary [&_ul_li]:text-[13px]',
          '[&_ol]:mb-3 [&_ol]:pl-5 [&_ol]:list-decimal [&_ol_li]:mb-1 [&_ol_li]:text-text-secondary [&_ol_li]:text-[13px]',
          '[&_strong]:font-semibold [&_strong]:text-text-primary',
          '[&_em]:italic',
          '[&_blockquote]:border-l-2 [&_blockquote]:border-accent [&_blockquote]:pl-3 [&_blockquote]:italic [&_blockquote]:text-text-tertiary [&_blockquote]:my-3',
          '[&_table]:w-full [&_table]:border-collapse [&_table]:my-3',
          '[&_th]:text-[10px] [&_th]:font-medium [&_th]:uppercase [&_th]:tracking-[0.06em] [&_th]:text-text-tertiary [&_th]:text-left [&_th]:p-[6px_10px] [&_th]:border-b [&_th]:border-border',
          '[&_td]:text-[12px] [&_td]:p-[6px_10px] [&_td]:border-b [&_td]:border-border-subtle',
          '[&_hr]:border-border [&_hr]:my-4',
          '[&_a]:text-accent [&_a]:underline',
        )}
        contentEditable
        suppressContentEditableWarning
        onMouseUp={handleSelection}
        onKeyUp={handleSelection}
        onInput={handleInput}
        onPaste={handlePaste}
        onBlur={() => setTimeout(() => setShowToolbar(false), 200)}
      />
    </div>
  );
}

function ToolbarButton({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onMouseDown={(e) => {
        e.preventDefault();
        onClick();
      }}
      className="h-[26px] px-2 text-[11px] text-text-secondary hover:bg-surface rounded-sm flex items-center gap-1 transition-colors duration-100 cursor-pointer whitespace-nowrap"
      title={label}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

// Markdown to HTML converter
function markdownToHtml(md: string): string {
  let html = md;

  // Horizontal rules
  html = html.replace(/^---$/gm, '<hr/>');

  // Headers (process from h4 down to h1)
  html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // Bold and italic
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Links — [text](url)
  html = html.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2">$1</a>');

  // Inline citations — [Source Name, Year]
  html = html.replace(/\[([^\]]+?(?:,\s*\d{4})[^\]]*)\]/g, '<span class="text-[10px] text-text-tertiary">[$1]</span>');

  // Tables
  html = html.replace(
    /(?:^(\|.+\|)\n(\|[-| :]+\|)\n((?:\|.+\|\n?)+))/gm,
    (_match, headerRow: string, _separator: string, bodyRows: string) => {
      const headers = headerRow.split('|').filter((c: string) => c.trim()).map((c: string) => `<th>${c.trim()}</th>`).join('');
      const rows = bodyRows.trim().split('\n').map((row: string) => {
        const cells = row.split('|').filter((c: string) => c.trim()).map((c: string) => `<td>${c.trim()}</td>`).join('');
        return `<tr>${cells}</tr>`;
      }).join('');
      return `<table><thead><tr>${headers}</tr></thead><tbody>${rows}</tbody></table>`;
    }
  );

  // Unordered lists
  html = html.replace(/(?:^- .+$\n?)+/gm, (match) => {
    const items = match.trim().split('\n').map((line) => `<li>${line.replace(/^- /, '')}</li>`).join('');
    return `<ul>${items}</ul>`;
  });

  // Ordered lists
  html = html.replace(/(?:^\d+\. .+$\n?)+/gm, (match) => {
    const items = match.trim().split('\n').map((line) => `<li>${line.replace(/^\d+\. /, '')}</li>`).join('');
    return `<ol>${items}</ol>`;
  });

  // Blockquotes
  html = html.replace(/(?:^> .+$\n?)+/gm, (match) => {
    const text = match.trim().split('\n').map((line) => line.replace(/^> /, '')).join('<br/>');
    return `<blockquote>${text}</blockquote>`;
  });

  // Paragraphs
  html = html.split('\n\n').map((block) => {
    const trimmed = block.trim();
    if (!trimmed) return '';
    if (/^<(h[1-4]|ul|ol|table|hr|blockquote)/.test(trimmed)) return trimmed;
    return `<p>${trimmed.replace(/\n/g, '<br/>')}</p>`;
  }).join('\n');

  return html;
}
