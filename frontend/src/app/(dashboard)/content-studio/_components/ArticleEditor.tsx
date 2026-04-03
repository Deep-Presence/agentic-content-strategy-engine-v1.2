'use client';

import { useMemo } from 'react';
import { useCreateBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/shadcn';
import '@blocknote/shadcn/style.css';
import {
  Bold, Italic, Underline, Strikethrough, Link2, List, ListOrdered,
  Quote, Code, Heading2, Heading3, AlignLeft, AlignCenter, AlignRight,
  Undo2, Redo2, Type,
} from 'lucide-react';
import type { ArticleSection } from './types';

function sectionsToBlocks(sections: ArticleSection[]) {
  const blocks: Array<Record<string, unknown>> = [];

  for (const section of sections) {
    blocks.push({
      type: 'heading',
      props: { level: 2 },
      content: [{ type: 'text', text: section.heading, styles: {} }],
    });

    const paragraphs = section.content.split('\n\n').filter(Boolean);
    for (const para of paragraphs) {
      blocks.push({
        type: 'paragraph',
        content: [{ type: 'text', text: para, styles: {} }],
      });
    }
  }

  return blocks;
}

interface ToolbarButtonProps {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
}

function ToolbarButton({ icon, label, active, onClick }: ToolbarButtonProps) {
  return (
    <button
      onClick={onClick}
      title={label}
      style={{
        width: 30,
        height: 30,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: active ? 'var(--accent-subtle)' : 'transparent',
        color: active ? 'var(--accent)' : 'var(--text-secondary)',
        border: 'none',
        borderRadius: 'var(--radius-sm)',
        cursor: 'pointer',
        transition: 'all 0.1s',
      }}
      onMouseEnter={(e) => {
        if (!active) (e.currentTarget as HTMLElement).style.background = 'var(--bg)';
      }}
      onMouseLeave={(e) => {
        if (!active) (e.currentTarget as HTMLElement).style.background = 'transparent';
      }}
    >
      {icon}
    </button>
  );
}

function ToolbarDivider() {
  return <div style={{ width: 1, height: 20, background: 'var(--border)', margin: '0 4px' }} />;
}

interface ArticleEditorProps {
  sections: ArticleSection[];
}

export function ArticleEditor({ sections }: ArticleEditorProps) {
  const initialContent = useMemo(() => sectionsToBlocks(sections), [sections]);

  /* eslint-disable @typescript-eslint/no-explicit-any */
  const editor = useCreateBlockNote({
    initialContent: initialContent,
  } as any);

  return (
    <div className="flex flex-col h-full">
      {/* Editor area — fills available space */}
      <div
        className="flex-1 overflow-y-auto"
        style={{ padding: '12px 24px 80px' }}
      >
        <BlockNoteView
          editor={editor as any}
          theme="light"
        />
      </div>

      {/* Fixed bottom editing toolbar */}
      <div
        className="flex-shrink-0 flex items-center gap-0.5 px-4"
        style={{
          height: 44,
          background: 'var(--surface)',
          borderTop: '1px solid var(--border)',
          position: 'sticky',
          bottom: 0,
          zIndex: 10,
        }}
      >
        {/* Undo / Redo */}
        <ToolbarButton icon={<Undo2 size={14} strokeWidth={1.5} />} label="Undo" />
        <ToolbarButton icon={<Redo2 size={14} strokeWidth={1.5} />} label="Redo" />

        <ToolbarDivider />

        {/* Text style */}
        <ToolbarButton icon={<Type size={14} strokeWidth={1.5} />} label="Paragraph" />
        <ToolbarButton icon={<Heading2 size={14} strokeWidth={1.5} />} label="Heading 2" />
        <ToolbarButton icon={<Heading3 size={14} strokeWidth={1.5} />} label="Heading 3" />

        <ToolbarDivider />

        {/* Inline formatting */}
        <ToolbarButton icon={<Bold size={14} strokeWidth={2} />} label="Bold" />
        <ToolbarButton icon={<Italic size={14} strokeWidth={1.5} />} label="Italic" />
        <ToolbarButton icon={<Underline size={14} strokeWidth={1.5} />} label="Underline" />
        <ToolbarButton icon={<Strikethrough size={14} strokeWidth={1.5} />} label="Strikethrough" />
        <ToolbarButton icon={<Code size={14} strokeWidth={1.5} />} label="Inline code" />
        <ToolbarButton icon={<Link2 size={14} strokeWidth={1.5} />} label="Link" />

        <ToolbarDivider />

        {/* Block types */}
        <ToolbarButton icon={<List size={14} strokeWidth={1.5} />} label="Bullet list" />
        <ToolbarButton icon={<ListOrdered size={14} strokeWidth={1.5} />} label="Numbered list" />
        <ToolbarButton icon={<Quote size={14} strokeWidth={1.5} />} label="Blockquote" />

        <ToolbarDivider />

        {/* Alignment */}
        <ToolbarButton icon={<AlignLeft size={14} strokeWidth={1.5} />} label="Align left" active />
        <ToolbarButton icon={<AlignCenter size={14} strokeWidth={1.5} />} label="Align center" />
        <ToolbarButton icon={<AlignRight size={14} strokeWidth={1.5} />} label="Align right" />

        {/* Word count on far right */}
        <div className="ml-auto flex items-center gap-3">
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>
            {sections.reduce((s, sec) => s + sec.words, 0).toLocaleString()} words
          </span>
        </div>
      </div>
    </div>
  );
  /* eslint-enable @typescript-eslint/no-explicit-any */
}
