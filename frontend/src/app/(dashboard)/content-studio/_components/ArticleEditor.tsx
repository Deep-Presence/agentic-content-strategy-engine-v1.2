'use client';

import { useMemo, useEffect, useRef, useState, useCallback } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import { Table, TableRow, TableCell, TableHeader } from '@tiptap/extension-table';
import { CommentMark } from './CommentMark';
import { marked } from 'marked';
import { MarkdownSerializer } from 'prosemirror-markdown';
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
  MessageSquare,
  X,
} from 'lucide-react';
import type { ArticleSection, ReviewComment } from './types';
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

function markdownToHTML(markdown: string): string {
  return marked.parse(markdown, { async: false }) as string;
}

function backticksFor(text: string, side: -1 | 1): string {
  const matches = text.match(/`+/g) || [];
  const len = matches.reduce((max, part) => Math.max(max, part.length), 0);
  let result = len > 0 && side > 0 ? ' `' : '`';
  for (let i = 0; i < len; i += 1) result += '`';
  if (len > 0 && side < 0) result += ' ';
  return result;
}

const tiptapMarkdownSerializer = new MarkdownSerializer(
  {
    blockquote(state, node) {
      state.wrapBlock('> ', null, node, () => state.renderContent(node));
    },
    bulletList(state, node) {
      state.renderList(node, '  ', () => '* ');
    },
    orderedList(state, node) {
      const start = Number(node.attrs.start || node.attrs.order || 1);
      const maxWidth = String(start + node.childCount - 1).length;
      const space = ' '.repeat(maxWidth + 2);
      state.renderList(node, space, (index) => {
        const value = String(start + index);
        return `${' '.repeat(maxWidth - value.length)}${value}. `;
      });
    },
    listItem(state, node) {
      state.renderContent(node);
    },
    paragraph(state, node) {
      state.renderInline(node);
      state.closeBlock(node);
    },
    heading(state, node) {
      state.write(`${'#'.repeat(node.attrs.level)} `);
      state.renderInline(node, false);
      state.closeBlock(node);
    },
    hardBreak(state, node, parent, index) {
      for (let i = index + 1; i < parent.childCount; i += 1) {
        if (parent.child(i).type !== node.type) {
          state.write('\\\n');
          return;
        }
      }
    },
    horizontalRule(state, node) {
      state.write(node.attrs.markup || '---');
      state.closeBlock(node);
    },
    codeBlock(state, node) {
      const backticks = node.textContent.match(/`{3,}/gm);
      const fence = backticks ? `${backticks.sort().slice(-1)[0]}\`` : '```';
      state.write(`${fence}${node.attrs.language || node.attrs.params || ''}\n`);
      state.text(node.textContent, false);
      state.write('\n');
      state.write(fence);
      state.closeBlock(node);
    },
    table(state, node) {
      const rows: string[][] = [];
      node.forEach((row) => {
        const cells: string[] = [];
        row.forEach((cell) => {
          const text = cell.textContent.replace(/\n+/g, ' ').trim();
          cells.push(text);
        });
        rows.push(cells);
      });
      if (rows.length === 0) {
        state.closeBlock(node);
        return;
      }
      const header = rows[0];
      state.write(`| ${header.join(' | ')} |\n`);
      state.write(`| ${header.map(() => '---').join(' | ')} |\n`);
      rows.slice(1).forEach((row) => {
        state.write(`| ${row.join(' | ')} |\n`);
      });
      state.closeBlock(node);
    },
    tableRow() {},
    tableCell(state, node) {
      state.renderInline(node, false);
    },
    tableHeader(state, node) {
      state.renderInline(node, false);
    },
    text(state, node) {
      state.text(node.text ?? '', false);
    },
  },
  {
    italic: { open: '*', close: '*', mixable: true, expelEnclosingWhitespace: true },
    bold: { open: '**', close: '**', mixable: true, expelEnclosingWhitespace: true },
    strike: { open: '~~', close: '~~', mixable: true, expelEnclosingWhitespace: true },
    link: {
      open: '[',
      close(_state, mark) {
        const title = mark.attrs.title ? ` "${String(mark.attrs.title).replace(/"/g, '\\"')}"` : '';
        return `](${String(mark.attrs.href).replace(/[\(\)"]/g, '\\$&')}${title})`;
      },
      mixable: true,
    },
    code: {
      open(_state, mark, parent, index) {
        return backticksFor(parent.child(index).text ?? '', -1);
      },
      close(_state, _mark, parent, index) {
        return backticksFor(parent.child(index - 1).text ?? '', 1);
      },
      escape: false,
    },
    underline: { open: '', close: '', mixable: true },
    comment: { open: '', close: '', mixable: true },
  },
);

// ---------------------------------------------------------------------------
// Bubble menu — appears on text selection (like Linear)
// ---------------------------------------------------------------------------

interface PendingComment {
  id: string;
  selectedText: string;
  coords: { top: number; left: number };
}

function useBubbleMenu(editor: Editor | null) {
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);

  const update = useCallback(() => {
    if (!editor) { setCoords(null); return; }
    const { from, to, empty } = editor.state.selection;
    if (empty || from === to) { setCoords(null); return; }

    const view = editor.view;
    const start = view.coordsAtPos(from);
    const end = view.coordsAtPos(to);
    const left = (start.left + end.left) / 2;
    const top = start.top - 8;
    setCoords({ top, left });
  }, [editor]);

  useEffect(() => {
    if (!editor) return;
    editor.on('selectionUpdate', update);
    // Don't hide on blur — clicking bubble menu buttons causes blur.
    // Instead, hide when selection becomes empty (handled in update).
    return () => {
      editor.off('selectionUpdate', update);
    };
  }, [editor, update]);

  return { coords };
}

function BubbleMenuBar({
  editor,
  isReviewMode,
  onAddComment,
}: {
  editor: Editor;
  isReviewMode?: boolean;
  onAddComment?: () => void;
}) {
  const { coords } = useBubbleMenu(editor);

  if (!coords) return null;

  return (
    <div
      className="flex items-center gap-0.5 px-1"
      onMouseDown={(e) => e.preventDefault()} // Prevent focus steal from editor
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
      {isReviewMode && onAddComment && (
        <>
          <div style={{ width: 1, height: 16, background: 'var(--border)', margin: '0 2px' }} />
          <BubbleBtn
            icon={<MessageSquare size={13} strokeWidth={2} />}
            label="Add Comment"
            active={false}
            onClick={onAddComment}
          />
        </>
      )}
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
// Comment input popover — appears after clicking "Add Comment"
// ---------------------------------------------------------------------------

function CommentInputPopover({
  pending,
  onAdd,
  onCancel,
}: {
  pending: PendingComment;
  onAdd: (feedback: string) => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && text.trim()) onAdd(text.trim());
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onCancel, onAdd, text]);

  // Flip above if near bottom
  const flipAbove = pending.coords.top + 180 > (typeof window !== 'undefined' ? window.innerHeight : 900);

  return (
    <div
      onMouseDown={(e) => e.stopPropagation()} // Don't interfere with editor
      style={{
        position: 'fixed',
        top: flipAbove ? pending.coords.top - 8 : pending.coords.top + 24,
        left: pending.coords.left,
        transform: flipAbove ? 'translate(-50%, -100%)' : 'translateX(-50%)',
        width: 300,
        background: 'var(--surface-raised)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        boxShadow: 'var(--shadow-float)',
        zIndex: 60,
        animation: 'fadeIn 0.12s ease',
        overflow: 'hidden',
      }}
    >
      <div style={{ padding: '8px 10px 4px', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)' }}>
        Add comment
      </div>
      <div style={{ padding: '0 10px 8px' }}>
        <div
          style={{
            fontSize: 11,
            color: 'var(--text-secondary)',
            background: 'var(--accent-subtle)',
            padding: '4px 8px',
            borderRadius: 4,
            marginBottom: 8,
            maxHeight: 40,
            overflow: 'hidden',
            fontStyle: 'italic',
          }}
        >
          &ldquo;{pending.selectedText.length > 80 ? pending.selectedText.slice(0, 80) + '...' : pending.selectedText}&rdquo;
        </div>
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="What should change?"
          rows={3}
          style={{
            width: '100%',
            fontSize: 12,
            lineHeight: 1.5,
            padding: '6px 8px',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--bg)',
            color: 'var(--text-primary)',
            outline: 'none',
            resize: 'vertical',
          }}
        />
        <div className="flex items-center justify-end gap-2" style={{ marginTop: 6 }}>
          <button
            onClick={onCancel}
            style={{
              height: 26,
              padding: '0 10px',
              fontSize: 11,
              fontWeight: 500,
              background: 'transparent',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={() => { if (text.trim()) onAdd(text.trim()); }}
            disabled={!text.trim()}
            style={{
              height: 26,
              padding: '0 10px',
              fontSize: 11,
              fontWeight: 500,
              background: text.trim() ? 'var(--accent)' : 'var(--border)',
              color: text.trim() ? 'var(--text-on-accent)' : 'var(--text-tertiary)',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: text.trim() ? 'pointer' : 'default',
            }}
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Comment list panel — shows all inline comments
// ---------------------------------------------------------------------------

function CommentListPanel({
  comments,
  onDelete,
  onClickComment,
}: {
  comments: ReviewComment[];
  onDelete: (id: string) => void;
  onClickComment: (id: string) => void;
}) {
  if (comments.length === 0) return null;

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: '0 48px 16px' }}>
      <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
        Review Comments ({comments.length})
      </div>
      <div className="space-y-2">
        {comments.map((c, i) => (
          <div
            key={c.id}
            className="flex items-start gap-2 group"
            style={{
              padding: '8px 10px',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--surface)',
              cursor: 'pointer',
            }}
            onClick={() => onClickComment(c.id)}
          >
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                fontFamily: 'var(--font-mono)',
                color: 'var(--accent)',
                background: 'var(--accent-subtle)',
                width: 20,
                height: 20,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: 4,
                flexShrink: 0,
                marginTop: 1,
              }}
            >
              {i + 1}
            </span>
            <div className="flex-1 min-w-0">
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--text-tertiary)',
                  fontStyle: 'italic',
                  marginBottom: 2,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                &ldquo;{c.selectedText.length > 60 ? c.selectedText.slice(0, 60) + '...' : c.selectedText}&rdquo;
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5 }}>
                {c.feedback}
              </div>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(c.id); }}
              title="Delete comment"
              style={{
                width: 20,
                height: 20,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'transparent',
                border: 'none',
                borderRadius: 4,
                color: 'var(--text-tertiary)',
                cursor: 'pointer',
                opacity: 0.5,
                flexShrink: 0,
                marginTop: 1,
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = '1'; (e.currentTarget as HTMLElement).style.color = 'var(--error)'; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = '0.5'; (e.currentTarget as HTMLElement).style.color = 'var(--text-tertiary)'; }}
            >
              <X size={12} strokeWidth={2} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bottom toolbar button
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
  initialMarkdown?: string;
  isReviewMode?: boolean;
  readOnly?: boolean;
  comments?: ReviewComment[];
  onCommentsChange?: (comments: ReviewComment[]) => void;
  overallReview?: string;
  onOverallReviewChange?: (text: string) => void;
  onMarkdownChange?: (markdown: string) => void;
}

export function ArticleEditor({
  sections,
  initialMarkdown,
  isReviewMode,
  readOnly = false,
  comments = [],
  onCommentsChange,
  overallReview = '',
  onOverallReviewChange,
  onMarkdownChange,
}: ArticleEditorProps) {
  const initialHTML = useMemo(
    () => (initialMarkdown && initialMarkdown.trim()
      ? markdownToHTML(initialMarkdown)
      : sectionsToHTML(sections)),
    [initialMarkdown, sections],
  );
  const [pendingComment, setPendingComment] = useState<PendingComment | null>(null);
  const lastAppliedHTMLRef = useRef(initialHTML);

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
      ...(isReviewMode ? [CommentMark] : []),
    ],
    content: initialHTML,
    editable: !readOnly,
    editorProps: {
      attributes: {
        class: 'prose-editor focus:outline-none',
      },
    },
    onUpdate: ({ editor: nextEditor }) => {
      if (readOnly) return;
      try {
        onMarkdownChange?.(tiptapMarkdownSerializer.serialize(nextEditor.state.doc));
      } catch (error) {
        console.error('Failed to serialize editor markdown draft', error);
      }
    },
  }, [initialHTML, isReviewMode, onMarkdownChange, readOnly]);

  useEffect(() => {
    if (!editor) return;
    if (lastAppliedHTMLRef.current === initialHTML) return;
    editor.commands.setContent(initialHTML, { emitUpdate: false });
    lastAppliedHTMLRef.current = initialHTML;
  }, [editor, initialHTML]);

  const wordCount = editor
    ? editor.getText().split(/\s+/).filter(Boolean).length
    : fallbackWordCount;

  // Handle "Add Comment" from BubbleMenu
  const handleAddComment = useCallback(() => {
    if (!editor) return;
    const { from, to, empty } = editor.state.selection;
    if (empty || from === to) return;

    const selectedText = editor.state.doc.textBetween(from, to, ' ');
    const commentId = crypto.randomUUID();

    // Apply the highlight mark immediately
    editor.chain().focus().setComment({ commentId }).run();

    // Get coords for the popover
    const start = editor.view.coordsAtPos(from);
    const end = editor.view.coordsAtPos(to);

    setPendingComment({
      id: commentId,
      selectedText,
      coords: {
        top: end.bottom,
        left: (start.left + end.left) / 2,
      },
    });
  }, [editor]);

  // Confirm pending comment
  const handleConfirmComment = useCallback((feedback: string) => {
    if (!pendingComment) return;
    const newComment: ReviewComment = {
      id: pendingComment.id,
      selectedText: pendingComment.selectedText,
      feedback,
      createdAt: new Date().toISOString(),
    };
    onCommentsChange?.([...comments, newComment]);
    setPendingComment(null);
  }, [pendingComment, comments, onCommentsChange]);

  // Cancel pending comment — remove mark
  const handleCancelComment = useCallback(() => {
    if (!pendingComment || !editor) return;
    editor.commands.unsetCommentById(pendingComment.id);
    setPendingComment(null);
  }, [pendingComment, editor]);

  // Delete a comment
  const handleDeleteComment = useCallback((id: string) => {
    if (!editor) return;
    editor.commands.unsetCommentById(id);
    onCommentsChange?.(comments.filter((c) => c.id !== id));
  }, [editor, comments, onCommentsChange]);

  // Click a comment in the list — scroll to its mark in the editor
  const handleClickComment = useCallback((commentId: string) => {
    if (!editor) return;
    const markType = editor.schema.marks.comment;
    if (!markType) return;

    let targetPos: number | null = null;
    editor.state.doc.descendants((node, pos) => {
      if (targetPos !== null) return false;
      if (!node.isText) return;
      const mark = node.marks.find(
        (m) => m.type === markType && m.attrs.commentId === commentId,
      );
      if (mark) targetPos = pos;
    });

    if (targetPos !== null) {
      editor.commands.focus();
      editor.commands.setTextSelection(targetPos);
      // Scroll into view
      const coords = editor.view.coordsAtPos(targetPos);
      const scrollContainer = editor.view.dom.closest('.overflow-y-auto');
      if (scrollContainer) {
        const containerRect = scrollContainer.getBoundingClientRect();
        const scrollOffset = coords.top - containerRect.top - containerRect.height / 3;
        scrollContainer.scrollBy({ top: scrollOffset, behavior: 'smooth' });
      }
    }
  }, [editor]);

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
            padding: '48px 48px 40px',
          }}
        >
          <BubbleMenuBar
            editor={editor}
            isReviewMode={isReviewMode && !readOnly}
            onAddComment={handleAddComment}
          />
          {pendingComment && (
            <CommentInputPopover
              pending={pendingComment}
              onAdd={handleConfirmComment}
              onCancel={handleCancelComment}
            />
          )}
          <EditorContent editor={editor} className="tiptap-editor" />
        </div>

        {/* Comment list + Overall review — inside scroll area */}
        {isReviewMode && !readOnly && (
          <>
            <CommentListPanel
              comments={comments}
              onDelete={handleDeleteComment}
              onClickComment={handleClickComment}
            />

            {/* Overall review textarea */}
            <div style={{ maxWidth: 720, margin: '0 auto', padding: '0 48px 32px' }}>
              <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
                <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)', background: 'var(--bg)' }}>
                  <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)' }}>
                    Overall Review
                  </span>
                </div>
                <textarea
                  value={overallReview}
                  onChange={(e) => onOverallReviewChange?.(e.target.value)}
                  placeholder="General feedback about the article..."
                  rows={3}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    fontSize: 12,
                    lineHeight: 1.6,
                    border: 'none',
                    outline: 'none',
                    resize: 'vertical',
                    background: 'var(--surface)',
                    color: 'var(--text-primary)',
                  }}
                />
              </div>
            </div>
          </>
        )}
      </div>

      {/* Fixed bottom toolbar */}
      {!readOnly && (
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
          <ToolbarButton icon={<Undo2 size={14} strokeWidth={1.5} />} label="Undo" disabled={!editor.can().undo()} onClick={() => editor.chain().focus().undo().run()} />
          <ToolbarButton icon={<Redo2 size={14} strokeWidth={1.5} />} label="Redo" disabled={!editor.can().redo()} onClick={() => editor.chain().focus().redo().run()} />
          <ToolbarDivider />
          <ToolbarButton icon={<Type size={14} strokeWidth={1.5} />} label="Paragraph" active={!editor.isActive('heading')} onClick={() => editor.chain().focus().setParagraph().run()} />
          <ToolbarButton icon={<Heading2 size={14} strokeWidth={1.5} />} label="Heading 2" active={editor.isActive('heading', { level: 2 })} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} />
          <ToolbarButton icon={<Heading3 size={14} strokeWidth={1.5} />} label="Heading 3" active={editor.isActive('heading', { level: 3 })} onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()} />
          <ToolbarDivider />
          <ToolbarButton icon={<Bold size={14} strokeWidth={2} />} label="Bold" active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()} />
          <ToolbarButton icon={<Italic size={14} strokeWidth={1.5} />} label="Italic" active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()} />
          <ToolbarButton icon={<UnderlineIcon size={14} strokeWidth={1.5} />} label="Underline" active={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()} />
          <ToolbarButton icon={<Strikethrough size={14} strokeWidth={1.5} />} label="Strikethrough" active={editor.isActive('strike')} onClick={() => editor.chain().focus().toggleStrike().run()} />
          <ToolbarButton icon={<Code size={14} strokeWidth={1.5} />} label="Inline code" active={editor.isActive('code')} onClick={() => editor.chain().focus().toggleCode().run()} />
          <ToolbarButton icon={<Link2 size={14} strokeWidth={1.5} />} label="Link" active={editor.isActive('link')} onClick={() => { if (editor.isActive('link')) { editor.chain().focus().unsetLink().run(); } else { const url = window.prompt('URL'); if (url) editor.chain().focus().setLink({ href: url }).run(); } }} />
          <ToolbarDivider />
          <ToolbarButton icon={<List size={14} strokeWidth={1.5} />} label="Bullet list" active={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()} />
          <ToolbarButton icon={<ListOrdered size={14} strokeWidth={1.5} />} label="Numbered list" active={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()} />
          <ToolbarButton icon={<Quote size={14} strokeWidth={1.5} />} label="Blockquote" active={editor.isActive('blockquote')} onClick={() => editor.chain().focus().toggleBlockquote().run()} />
          <ToolbarDivider />
          <ToolbarButton icon={<AlignLeft size={14} strokeWidth={1.5} />} label="Align left" active={editor.isActive({ textAlign: 'left' })} onClick={() => editor.chain().focus().setTextAlign('left').run()} />
          <ToolbarButton icon={<AlignCenter size={14} strokeWidth={1.5} />} label="Align center" active={editor.isActive({ textAlign: 'center' })} onClick={() => editor.chain().focus().setTextAlign('center').run()} />
          <ToolbarButton icon={<AlignRight size={14} strokeWidth={1.5} />} label="Align right" active={editor.isActive({ textAlign: 'right' })} onClick={() => editor.chain().focus().setTextAlign('right').run()} />
          <div className="ml-auto flex items-center gap-3">
            {isReviewMode && comments.length > 0 && (
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
                {comments.length} comment{comments.length !== 1 ? 's' : ''}
              </span>
            )}
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>
              {wordCount.toLocaleString()} words
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
