'use client';

import { useMemo, useEffect, useRef, useState, useCallback } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import { Table, TableRow, TableCell, TableHeader } from '@tiptap/extension-table';
import { marked } from 'marked';
import {
  Bold,
  Italic,
  Underline as UnderlineIcon,
  Strikethrough,
  Link2,
  List,
  ListOrdered,
  Quote,
  Code,
  Heading2,
  Heading3,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Undo2,
  Redo2,
  Type,
} from 'lucide-react';
import type { ArticleSection } from './types';
import type { Editor } from '@tiptap/react';

// ---------------------------------------------------------------------------
// Convert ArticleSection[] → HTML string for Tiptap
// ---------------------------------------------------------------------------

function sectionsToHTML(sections: ArticleSection[]): string {
  const md = sections
    .map((s) => `## ${s.heading}\n\n${s.content}`)
    .join('\n\n---\n\n');

  return marked.parse(md, { async: false }) as string;
}

// ---------------------------------------------------------------------------
// Bubble menu — appears on text selection (like Linear)
// ---------------------------------------------------------------------------

function useBubbleMenu(editor: Editor | null) {
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const update = useCallback(() => {
    if (!editor) { setCoords(null); return; }
    const { from, to, empty } = editor.state.selection;
    if (empty || from === to) { setCoords(null); return; }

    const view = editor.view;
    const start = view.coordsAtPos(from);
    const end = view.coordsAtPos(to);
    const left = (start.left + end.left) / 2;
    const top = start.top - 8; // above selection
    setCoords({ top, left });
  }, [editor]);

  useEffect(() => {
    if (!editor) return;
    editor.on('selectionUpdate', update);
    editor.on('blur', () => setCoords(null));
    return () => {
      editor.off('selectionUpdate', update);
    };
  }, [editor, update]);

  return { coords, menuRef };
}

function BubbleMenuBar({ editor }: { editor: Editor }) {
  const { coords, menuRef } = useBubbleMenu(editor);

  if (!coords) return null;

  return (
    <div
      ref={menuRef}
      className="flex items-center gap-0.5 px-1"
      style={{
        position: 'fixed',
        top: coords.top,
        left: coords.left,
        transform: 'translate(-50%, -100%)',
        height: 34,
        background: 'var(--surface-raised)',
        border: '1px solid var(--border)',
        borderRadius: 8,
        boxShadow: 'var(--shadow-float)',
        zIndex: 50,
        animation: 'fadeIn 0.12s ease',
      }}
    >
      <BubbleBtn
        icon={<Bold size={13} strokeWidth={2.5} />}
        label="Bold"
        active={editor.isActive('bold')}
        onClick={() => editor.chain().focus().toggleBold().run()}
      />
      <BubbleBtn
        icon={<Italic size={13} strokeWidth={2} />}
        label="Italic"
        active={editor.isActive('italic')}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      />
      <BubbleBtn
        icon={<UnderlineIcon size={13} strokeWidth={2} />}
        label="Underline"
        active={editor.isActive('underline')}
        onClick={() => editor.chain().focus().toggleUnderline().run()}
      />
      <BubbleBtn
        icon={<Strikethrough size={13} strokeWidth={2} />}
        label="Strikethrough"
        active={editor.isActive('strike')}
        onClick={() => editor.chain().focus().toggleStrike().run()}
      />
      <div style={{ width: 1, height: 16, background: 'var(--border)', margin: '0 2px' }} />
      <BubbleBtn
        icon={<Code size={13} strokeWidth={2} />}
        label="Code"
        active={editor.isActive('code')}
        onClick={() => editor.chain().focus().toggleCode().run()}
      />
      <BubbleBtn
        icon={<Link2 size={13} strokeWidth={2} />}
        label="Link"
        active={editor.isActive('link')}
        onClick={() => {
          if (editor.isActive('link')) {
            editor.chain().focus().unsetLink().run();
          } else {
            const url = window.prompt('URL');
            if (url) editor.chain().focus().setLink({ href: url }).run();
          }
        }}
      />
    </div>
  );
}

function BubbleBtn({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      style={{
        width: 28,
        height: 28,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: active ? 'var(--accent-subtle)' : 'transparent',
        color: active ? 'var(--accent)' : 'var(--text-secondary)',
        border: 'none',
        borderRadius: 5,
        cursor: 'pointer',
        transition: 'all 0.1s',
      }}
    >
      {icon}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Bottom toolbar button (reused from previous implementation)
// ---------------------------------------------------------------------------

interface ToolbarButtonProps {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}

function ToolbarButton({ icon, label, active, disabled, onClick }: ToolbarButtonProps) {
  return (
    <button
      onClick={onClick}
      title={label}
      disabled={disabled}
      style={{
        width: 30,
        height: 30,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: active ? 'var(--accent-subtle)' : 'transparent',
        color: disabled
          ? 'var(--text-tertiary)'
          : active
            ? 'var(--accent)'
            : 'var(--text-secondary)',
        border: 'none',
        borderRadius: 'var(--radius-sm)',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.4 : 1,
        transition: 'all 0.1s',
      }}
      onMouseEnter={(e) => {
        if (!active && !disabled) (e.currentTarget as HTMLElement).style.background = 'var(--bg)';
      }}
      onMouseLeave={(e) => {
        if (!active && !disabled) (e.currentTarget as HTMLElement).style.background = 'transparent';
      }}
    >
      {icon}
    </button>
  );
}

function ToolbarDivider() {
  return <div style={{ width: 1, height: 20, background: 'var(--border)', margin: '0 4px' }} />;
}

// ---------------------------------------------------------------------------
// Main editor component
// ---------------------------------------------------------------------------

interface ArticleEditorProps {
  sections: ArticleSection[];
}

export function ArticleEditor({ sections }: ArticleEditorProps) {
  const initialHTML = useMemo(() => sectionsToHTML(sections), [sections]);

  const fallbackWordCount = useMemo(
    () => sections.reduce((s, sec) => s + sec.words, 0),
    [sections],
  );

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Underline,
      TextAlign.configure({
        types: ['heading', 'paragraph'],
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: { class: 'editor-link' },
      }),
      Placeholder.configure({
        placeholder: 'Start writing...',
      }),
      Table.configure({ resizable: false }),
      TableRow,
      TableCell,
      TableHeader,
    ],
    content: initialHTML,
    editorProps: {
      attributes: {
        class: 'prose-editor focus:outline-none',
      },
    },
  });

  const wordCount = editor
    ? editor.getText().split(/\s+/).filter(Boolean).length
    : fallbackWordCount;

  if (!editor) return null;

  return (
    <div className="flex flex-col h-full">
      {/* Editor area — centered reading column */}
      <div
        className="flex-1 overflow-y-auto"
        style={{ background: 'var(--bg)', scrollBehavior: 'smooth' }}
      >
        <div
          style={{
            maxWidth: 720,
            margin: '0 auto',
            padding: '48px 48px 120px',
          }}
        >
          <BubbleMenuBar editor={editor} />
          <EditorContent editor={editor} className="tiptap-editor" />
        </div>
      </div>

      {/* Fixed bottom toolbar */}
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
        <ToolbarButton
          icon={<Undo2 size={14} strokeWidth={1.5} />}
          label="Undo"
          disabled={!editor.can().undo()}
          onClick={() => editor.chain().focus().undo().run()}
        />
        <ToolbarButton
          icon={<Redo2 size={14} strokeWidth={1.5} />}
          label="Redo"
          disabled={!editor.can().redo()}
          onClick={() => editor.chain().focus().redo().run()}
        />

        <ToolbarDivider />

        {/* Text style */}
        <ToolbarButton
          icon={<Type size={14} strokeWidth={1.5} />}
          label="Paragraph"
          active={!editor.isActive('heading')}
          onClick={() => editor.chain().focus().setParagraph().run()}
        />
        <ToolbarButton
          icon={<Heading2 size={14} strokeWidth={1.5} />}
          label="Heading 2"
          active={editor.isActive('heading', { level: 2 })}
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        />
        <ToolbarButton
          icon={<Heading3 size={14} strokeWidth={1.5} />}
          label="Heading 3"
          active={editor.isActive('heading', { level: 3 })}
          onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
        />

        <ToolbarDivider />

        {/* Inline formatting */}
        <ToolbarButton
          icon={<Bold size={14} strokeWidth={2} />}
          label="Bold"
          active={editor.isActive('bold')}
          onClick={() => editor.chain().focus().toggleBold().run()}
        />
        <ToolbarButton
          icon={<Italic size={14} strokeWidth={1.5} />}
          label="Italic"
          active={editor.isActive('italic')}
          onClick={() => editor.chain().focus().toggleItalic().run()}
        />
        <ToolbarButton
          icon={<UnderlineIcon size={14} strokeWidth={1.5} />}
          label="Underline"
          active={editor.isActive('underline')}
          onClick={() => editor.chain().focus().toggleUnderline().run()}
        />
        <ToolbarButton
          icon={<Strikethrough size={14} strokeWidth={1.5} />}
          label="Strikethrough"
          active={editor.isActive('strike')}
          onClick={() => editor.chain().focus().toggleStrike().run()}
        />
        <ToolbarButton
          icon={<Code size={14} strokeWidth={1.5} />}
          label="Inline code"
          active={editor.isActive('code')}
          onClick={() => editor.chain().focus().toggleCode().run()}
        />
        <ToolbarButton
          icon={<Link2 size={14} strokeWidth={1.5} />}
          label="Link"
          active={editor.isActive('link')}
          onClick={() => {
            if (editor.isActive('link')) {
              editor.chain().focus().unsetLink().run();
            } else {
              const url = window.prompt('URL');
              if (url) editor.chain().focus().setLink({ href: url }).run();
            }
          }}
        />

        <ToolbarDivider />

        {/* Block types */}
        <ToolbarButton
          icon={<List size={14} strokeWidth={1.5} />}
          label="Bullet list"
          active={editor.isActive('bulletList')}
          onClick={() => editor.chain().focus().toggleBulletList().run()}
        />
        <ToolbarButton
          icon={<ListOrdered size={14} strokeWidth={1.5} />}
          label="Numbered list"
          active={editor.isActive('orderedList')}
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
        />
        <ToolbarButton
          icon={<Quote size={14} strokeWidth={1.5} />}
          label="Blockquote"
          active={editor.isActive('blockquote')}
          onClick={() => editor.chain().focus().toggleBlockquote().run()}
        />

        <ToolbarDivider />

        {/* Alignment */}
        <ToolbarButton
          icon={<AlignLeft size={14} strokeWidth={1.5} />}
          label="Align left"
          active={editor.isActive({ textAlign: 'left' })}
          onClick={() => editor.chain().focus().setTextAlign('left').run()}
        />
        <ToolbarButton
          icon={<AlignCenter size={14} strokeWidth={1.5} />}
          label="Align center"
          active={editor.isActive({ textAlign: 'center' })}
          onClick={() => editor.chain().focus().setTextAlign('center').run()}
        />
        <ToolbarButton
          icon={<AlignRight size={14} strokeWidth={1.5} />}
          label="Align right"
          active={editor.isActive({ textAlign: 'right' })}
          onClick={() => editor.chain().focus().setTextAlign('right').run()}
        />

        {/* Word count */}
        <div className="ml-auto flex items-center gap-3">
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>
            {wordCount.toLocaleString()} words
          </span>
        </div>
      </div>
    </div>
  );
}
