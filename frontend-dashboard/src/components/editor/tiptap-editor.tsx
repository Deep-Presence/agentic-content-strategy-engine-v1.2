'use client';

import { useEditor, EditorContent } from '@tiptap/react';
import { BubbleMenu } from '@tiptap/react/menus';
import StarterKit from '@tiptap/starter-kit';
import Highlight from '@tiptap/extension-highlight';
import Underline from '@tiptap/extension-underline';
import Link from '@tiptap/extension-link';
import { TextStyle } from '@tiptap/extension-text-style';
import Color from '@tiptap/extension-color';
import { useState, useEffect, useCallback } from 'react';
import {
  Bold, Italic, Underline as UnderlineIcon, Strikethrough, Code,
  Heading1, Heading2, Heading3, Heading4, Pilcrow,
  List, ListOrdered, Quote, Minus, Braces, Highlighter,
  Undo, Redo, Maximize2, Minimize2,
  FileText, Hash, Clock, GraduationCap, Link2, Unlink,
} from 'lucide-react';
import { cn } from '@/lib/utils/cn';

interface TiptapEditorProps {
  content: string;
  editable?: boolean;
  onChange?: (html: string) => void;
  targetWordCount?: { min: number; max: number };
  className?: string;
}

interface ToolbarButtonProps {
  onClick: () => void;
  isActive?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
  title: string;
  shortcut?: string;
}

function ToolbarButton({ onClick, isActive, disabled, children, title, shortcut }: ToolbarButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={shortcut ? `${title} (${shortcut})` : title}
      className={cn(
        'relative p-1.5 rounded-md transition-all duration-100 group/btn',
        isActive
          ? 'bg-terracotta-100 text-terracotta-500'
          : 'text-cream-600 hover:bg-cream-200 hover:text-cream-900',
        disabled && 'opacity-30 pointer-events-none',
      )}
    >
      {children}
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-cream-950 text-white text-[10px] font-sans rounded whitespace-nowrap opacity-0 group-hover/btn:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg">
        {title}
        {shortcut && <span className="ml-1.5 text-cream-500">{shortcut}</span>}
      </span>
    </button>
  );
}

function Sep() {
  return <span className="w-px h-5 bg-cream-300 mx-1" />;
}

function BubbleBtn({
  onClick,
  isActive,
  children,
}: {
  onClick: () => void;
  isActive?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'p-1.5 rounded transition-colors',
        isActive ? 'bg-cream-700 text-white' : 'text-cream-400 hover:text-white',
      )}
    >
      {children}
    </button>
  );
}

function estimateGradeLevel(text: string): number {
  const sentences = text.split(/[.!?]+/).filter((s) => s.trim().length > 0);
  const words = text.split(/\s+/).filter((w) => w.length > 0);
  if (sentences.length === 0 || words.length === 0) return 0;
  const syllables = words.reduce((sum, word) => {
    const cleaned = word.toLowerCase().replace(/[^a-z]/g, '');
    if (cleaned.length <= 3) return sum + 1;
    const groups = cleaned.match(/[aeiouy]+/g);
    return sum + Math.max(1, groups?.length ?? 1);
  }, 0);
  const level = 0.39 * (words.length / sentences.length) + 11.8 * (syllables / words.length) - 15.59;
  return Math.max(0, Math.min(20, level));
}

interface EditorStats {
  words: number;
  chars: number;
  headings: number;
  grade: number;
}

export function TiptapEditor({
  content,
  editable = true,
  onChange,
  targetWordCount,
  className,
}: TiptapEditorProps) {
  const [focusMode, setFocusMode] = useState(false);
  const [stats, setStats] = useState<EditorStats>({ words: 0, chars: 0, headings: 0, grade: 0 });
  const [linkUrl, setLinkUrl] = useState('');
  const [showLinkInput, setShowLinkInput] = useState(false);

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3, 4] },
      }),
      Highlight.extend({
        addKeyboardShortcuts() {
          return {
            'Mod-Shift-h': () => this.editor.commands.toggleHighlight(),
          };
        },
      }).configure({ multicolor: true }),
      Underline,
      Link.configure({
        openOnClick: false,
        HTMLAttributes: { class: 'text-ocean-400 underline decoration-ocean-200 underline-offset-2 hover:decoration-ocean-400 cursor-pointer' },
      }),
      TextStyle,
      Color,
    ],
    content,
    editable,
    onUpdate: ({ editor: e }) => {
      onChange?.(e.getHTML());
    },
    editorProps: {
      attributes: {
        class: cn(
          'outline-none min-h-[500px] px-10 py-8',
          'font-body text-[0.938rem] leading-[1.8] text-cream-800',
          // Headings
          '[&_h1]:font-serif [&_h1]:text-[1.75rem] [&_h1]:font-semibold [&_h1]:text-cream-950 [&_h1]:mb-4 [&_h1]:mt-8 [&_h1]:leading-tight',
          '[&_h2]:font-serif [&_h2]:text-[1.35rem] [&_h2]:font-semibold [&_h2]:text-cream-900 [&_h2]:mb-3 [&_h2]:mt-7 [&_h2]:leading-snug [&_h2]:pb-1.5 [&_h2]:border-b [&_h2]:border-cream-200',
          '[&_h3]:font-serif [&_h3]:text-[1.1rem] [&_h3]:font-semibold [&_h3]:text-cream-800 [&_h3]:mb-2 [&_h3]:mt-5',
          '[&_h4]:font-sans [&_h4]:text-sm [&_h4]:font-semibold [&_h4]:text-cream-700 [&_h4]:mb-2 [&_h4]:mt-4 [&_h4]:uppercase [&_h4]:tracking-wide',
          // Paragraphs
          '[&_p]:mb-3 [&_p]:text-cream-800',
          // Lists
          '[&_ul]:my-3 [&_ul]:pl-5 [&_ul_li]:mb-1 [&_ul_li]:text-cream-800',
          '[&_ol]:my-3 [&_ol]:pl-5 [&_ol_li]:mb-1 [&_ol_li]:text-cream-800',
          // Blockquotes
          '[&_blockquote]:border-l-[3px] [&_blockquote]:border-terracotta-300 [&_blockquote]:bg-terracotta-50/30 [&_blockquote]:pl-4 [&_blockquote]:py-2 [&_blockquote]:my-4 [&_blockquote]:rounded-r [&_blockquote]:text-cream-700 [&_blockquote]:italic',
          // Code
          '[&_code]:text-ocean-500 [&_code]:bg-ocean-50 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-[0.85em] [&_code]:font-mono',
          // Pre
          '[&_pre]:bg-cream-950 [&_pre]:rounded-lg [&_pre]:text-cream-200 [&_pre]:p-4 [&_pre]:my-4 [&_pre]:overflow-x-auto [&_pre_code]:bg-transparent [&_pre_code]:text-cream-200 [&_pre_code]:p-0',
          // HR
          '[&_hr]:border-cream-300 [&_hr]:my-6',
          // Strong
          '[&_strong]:text-cream-950 [&_strong]:font-semibold',
          // Mark / Highlight
          '[&_mark]:bg-yellow-100 [&_mark]:rounded-sm [&_mark]:px-0.5',
          // Empty state placeholder
          '[&_p.is-editor-empty:first-child]:before:content-[attr(data-placeholder)] [&_p.is-editor-empty:first-child]:before:text-cream-400 [&_p.is-editor-empty:first-child]:before:float-left [&_p.is-editor-empty:first-child]:before:h-0 [&_p.is-editor-empty:first-child]:before:pointer-events-none',
        ),
      },
    },
  });

  // Compute stats on editor updates
  useEffect(() => {
    if (!editor) return;
    const update = () => {
      const text = editor.getText();
      const words = text.split(/\s+/).filter((w) => w.length > 0).length;
      const chars = text.length;
      const html = editor.getHTML();
      const headings = (html.match(/<h[1-4]/g) || []).length;
      const grade = estimateGradeLevel(text);
      setStats({ words, chars, headings, grade });
    };
    update();
    editor.on('update', update);
    return () => {
      editor.off('update', update);
    };
  }, [editor]);

  const setLink = useCallback(() => {
    if (!editor || !linkUrl) return;
    editor.chain().focus().extendMarkRange('link').setLink({ href: linkUrl }).run();
    setLinkUrl('');
    setShowLinkInput(false);
  }, [editor, linkUrl]);

  const removeLink = useCallback(() => {
    if (!editor) return;
    editor.chain().focus().extendMarkRange('link').unsetLink().run();
  }, [editor]);

  // Word count progress
  const wcProgress = targetWordCount && stats.words > 0
    ? {
        pct: Math.min(1, stats.words / ((targetWordCount.min + targetWordCount.max) / 2)),
        inRange: stats.words >= targetWordCount.min && stats.words <= targetWordCount.max,
        over: stats.words > targetWordCount.max,
      }
    : null;

  // Loading skeleton
  if (!editor) {
    return (
      <div className={cn('border border-[var(--border-default)] rounded-lg bg-white overflow-hidden', className)}>
        <div className="h-11 bg-cream-100 border-b border-[var(--border-default)]" />
        <div className="min-h-[500px] px-10 py-8 space-y-4 animate-pulse">
          <div className="h-7 w-3/4 bg-cream-200 rounded" />
          <div className="h-4 w-full bg-cream-100 rounded" />
          <div className="h-4 w-full bg-cream-100 rounded" />
          <div className="h-4 w-5/6 bg-cream-100 rounded" />
          <div className="h-6 w-1/2 bg-cream-200 rounded mt-6" />
          <div className="h-4 w-full bg-cream-100 rounded" />
          <div className="h-4 w-full bg-cream-100 rounded" />
          <div className="h-4 w-4/5 bg-cream-100 rounded" />
        </div>
        <div className="h-8 bg-cream-50 border-t border-[var(--border-default)]" />
      </div>
    );
  }

  return (
    <div
      className={cn(
        'flex flex-col border border-[var(--border-default)] rounded-lg bg-white overflow-hidden shadow-sm',
        'focus-within:border-terracotta-300 focus-within:shadow-[0_0_0_3px_rgba(217,119,87,0.08)]',
        'transition-all duration-200',
        className,
      )}
      onKeyDown={(e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
          e.preventDefault();
          if (editor.isActive('link')) {
            removeLink();
          } else {
            setShowLinkInput((prev) => !prev);
          }
        }
      }}
    >
      {/* ── Toolbar ── */}
      {editable && (
        <div className="sticky top-0 z-10 flex items-center gap-0.5 px-3 py-1.5 border-b border-[var(--border-default)] bg-cream-50/95 backdrop-blur-sm">
          {/* Text formatting */}
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBold().run()}
            isActive={editor.isActive('bold')}
            title="Bold"
            shortcut="⌘B"
          >
            <Bold className="h-4 w-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleItalic().run()}
            isActive={editor.isActive('italic')}
            title="Italic"
            shortcut="⌘I"
          >
            <Italic className="h-4 w-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleUnderline().run()}
            isActive={editor.isActive('underline')}
            title="Underline"
            shortcut="⌘U"
          >
            <UnderlineIcon className="h-4 w-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleStrike().run()}
            isActive={editor.isActive('strike')}
            title="Strikethrough"
            shortcut="⌘⇧S"
          >
            <Strikethrough className="h-4 w-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleCode().run()}
            isActive={editor.isActive('code')}
            title="Inline Code"
            shortcut="⌘E"
          >
            <Code className="h-4 w-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHighlight().run()}
            isActive={editor.isActive('highlight')}
            title="Highlight"
            shortcut="⌘⇧H"
          >
            <Highlighter className="h-4 w-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => {
              if (editor.isActive('link')) {
                removeLink();
              } else {
                setShowLinkInput(!showLinkInput);
              }
            }}
            isActive={editor.isActive('link')}
            title={editor.isActive('link') ? 'Remove Link' : 'Add Link'}
            shortcut="⌘K"
          >
            {editor.isActive('link') ? <Unlink className="h-4 w-4" /> : <Link2 className="h-4 w-4" />}
          </ToolbarButton>

          <Sep />

          {/* Headings */}
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
            isActive={editor.isActive('heading', { level: 1 })}
            title="Heading 1"
          >
            <Heading1 className="h-4 w-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            isActive={editor.isActive('heading', { level: 2 })}
            title="Heading 2"
          >
            <Heading2 className="h-4 w-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
            isActive={editor.isActive('heading', { level: 3 })}
            title="Heading 3"
          >
            <Heading3 className="h-4 w-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 4 }).run()}
            isActive={editor.isActive('heading', { level: 4 })}
            title="Heading 4"
          >
            <Heading4 className="h-4 w-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().setParagraph().run()}
            isActive={editor.isActive('paragraph') && !editor.isActive('bulletList') && !editor.isActive('orderedList') && !editor.isActive('blockquote')}
            title="Paragraph"
          >
            <Pilcrow className="h-4 w-4" />
          </ToolbarButton>

          <Sep />

          {/* Block elements */}
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            isActive={editor.isActive('bulletList')}
            title="Bullet List"
            shortcut="⌘⇧8"
          >
            <List className="h-4 w-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            isActive={editor.isActive('orderedList')}
            title="Ordered List"
            shortcut="⌘⇧7"
          >
            <ListOrdered className="h-4 w-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBlockquote().run()}
            isActive={editor.isActive('blockquote')}
            title="Blockquote"
            shortcut="⌘⇧B"
          >
            <Quote className="h-4 w-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleCodeBlock().run()}
            isActive={editor.isActive('codeBlock')}
            title="Code Block"
          >
            <Braces className="h-4 w-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().setHorizontalRule().run()}
            title="Divider"
          >
            <Minus className="h-4 w-4" />
          </ToolbarButton>

          <Sep />

          {/* History */}
          <ToolbarButton
            onClick={() => editor.chain().focus().undo().run()}
            disabled={!editor.can().undo()}
            title="Undo"
            shortcut="⌘Z"
          >
            <Undo className="h-4 w-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().redo().run()}
            disabled={!editor.can().redo()}
            title="Redo"
            shortcut="⌘⇧Z"
          >
            <Redo className="h-4 w-4" />
          </ToolbarButton>

          {/* Focus mode (right-aligned) */}
          <div className="ml-auto">
            <ToolbarButton
              onClick={() => setFocusMode(!focusMode)}
              isActive={focusMode}
              title={focusMode ? 'Exit Focus' : 'Focus Mode'}
            >
              {focusMode ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </ToolbarButton>
          </div>
        </div>
      )}

      {/* ── Link input bar ── */}
      {showLinkInput && (
        <div className="flex items-center gap-2 px-4 py-2 bg-ocean-50 border-b border-ocean-200">
          <Link2 className="h-4 w-4 text-ocean-400 shrink-0" />
          <input
            type="url"
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') setLink(); if (e.key === 'Escape') setShowLinkInput(false); }}
            placeholder="https://..."
            autoFocus
            className="flex-1 px-2 py-1 text-body-sm font-sans bg-white border border-ocean-200 rounded focus:outline-none focus:border-ocean-400 text-cream-900 placeholder:text-cream-400"
          />
          <button onClick={setLink} className="px-3 py-1 text-body-sm font-sans font-medium bg-ocean-400 text-white rounded hover:bg-ocean-500 transition-colors">
            Apply
          </button>
          <button onClick={() => setShowLinkInput(false)} className="px-2 py-1 text-body-sm font-sans text-cream-600 hover:text-cream-900 transition-colors">
            Cancel
          </button>
        </div>
      )}

      {/* ── Bubble Menu (floating toolbar on text selection) ── */}
      {editable && (
        <BubbleMenu
          editor={editor}
          className="flex items-center gap-0.5 px-1.5 py-1 bg-cream-950 rounded-lg shadow-xl border border-cream-800/50"
        >
          <BubbleBtn onClick={() => editor.chain().focus().toggleBold().run()} isActive={editor.isActive('bold')}>
            <Bold className="h-3.5 w-3.5" />
          </BubbleBtn>
          <BubbleBtn onClick={() => editor.chain().focus().toggleItalic().run()} isActive={editor.isActive('italic')}>
            <Italic className="h-3.5 w-3.5" />
          </BubbleBtn>
          <BubbleBtn onClick={() => editor.chain().focus().toggleUnderline().run()} isActive={editor.isActive('underline')}>
            <UnderlineIcon className="h-3.5 w-3.5" />
          </BubbleBtn>
          <BubbleBtn onClick={() => editor.chain().focus().toggleStrike().run()} isActive={editor.isActive('strike')}>
            <Strikethrough className="h-3.5 w-3.5" />
          </BubbleBtn>
          <span className="w-px h-4 bg-cream-700 mx-0.5" />
          <BubbleBtn onClick={() => editor.chain().focus().toggleCode().run()} isActive={editor.isActive('code')}>
            <Code className="h-3.5 w-3.5" />
          </BubbleBtn>
          <BubbleBtn onClick={() => editor.chain().focus().toggleHighlight().run()} isActive={editor.isActive('highlight')}>
            <Highlighter className="h-3.5 w-3.5" />
          </BubbleBtn>
        </BubbleMenu>
      )}

      {/* ── Editor content ── */}
      <div
        className={cn(
          'flex-1 overflow-y-auto',
          focusMode && 'max-w-[720px] mx-auto w-full',
        )}
      >
        <EditorContent editor={editor} />
      </div>

      {/* ── Status bar ── */}
      <div className="flex items-center justify-between px-4 py-1.5 border-t border-[var(--border-default)] bg-cream-50 select-none">
        <div className="flex items-center gap-3 text-[11px] font-sans text-cream-500">
          {/* Word count + progress */}
          <div className="flex items-center gap-1.5">
            <FileText className="h-3 w-3" />
            <span
              className={cn(
                'tabular-nums',
                wcProgress?.inRange && 'text-sage-400 font-medium',
                wcProgress?.over && 'text-error font-medium',
              )}
            >
              {stats.words.toLocaleString()}
            </span>
            {targetWordCount ? (
              <>
                <span className="text-cream-300">/</span>
                <span className="tabular-nums">{targetWordCount.min}–{targetWordCount.max}</span>
                {wcProgress && (
                  <div className="w-14 h-1 bg-cream-200 rounded-full overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full transition-all duration-300',
                        wcProgress.inRange ? 'bg-sage-400' : wcProgress.over ? 'bg-error' : 'bg-terracotta-400',
                      )}
                      style={{ width: `${Math.min(100, wcProgress.pct * 100)}%` }}
                    />
                  </div>
                )}
              </>
            ) : (
              <span>words</span>
            )}
          </div>

          <span className="text-cream-300">·</span>
          <span className="tabular-nums">{stats.chars.toLocaleString()} chars</span>

          <span className="text-cream-300">·</span>
          <div className="flex items-center gap-1">
            <Hash className="h-3 w-3" />
            <span className="tabular-nums">{stats.headings}</span>
          </div>
        </div>

        <div className="flex items-center gap-3 text-[11px] font-sans text-cream-500">
          <div className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            <span>{stats.words < 250 ? '<1' : Math.ceil(stats.words / 250)} min read</span>
          </div>
          <span className="text-cream-300">·</span>
          <div className="flex items-center gap-1">
            <GraduationCap className="h-3 w-3" />
            <span className="tabular-nums">Grade {stats.grade.toFixed(1)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
