'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { Card, Badge, Button } from '@/components/ui';
import {
  Search,
  Copy,
  Check,
  ChevronRight,
  Clock,
  RefreshCw,
  Loader2,
  Download,
  Upload,
  Edit3,
} from 'lucide-react';
import { MarkdownRenderer } from './MarkdownRenderer';
import { VersionHistory } from './VersionHistory';
import type { VersionEntry } from '../_lib/types';

interface SectionDetailProps {
  title: string;
  markdown: string;
  version: string;
  lastUpdated: string;
  createdBy: string;
  wordCount: number;
  tags?: string[];
  onBack: () => void;
  breadcrumb: string[];
  versions?: VersionEntry[];
  activeFilePath?: string;
  onSelectVersion?: (entry: VersionEntry) => void;
  onUpload?: () => void;
  onRegenerate?: () => void;
  isRegenerating?: boolean;
}

interface Heading { id: string; text: string; level: number; }

const TAG_COLORS = [
  'bg-info-subtle text-info border-info/20',
  'bg-accent-subtle text-accent border-accent/20',
  'bg-success-subtle text-success border-success/20',
  'bg-warning-subtle text-warning border-warning/20',
  'bg-error-subtle text-error border-error/20',
];

export function SectionDetail({
  title,
  markdown,
  version,
  lastUpdated,
  createdBy,
  wordCount,
  tags = [],
  onBack,
  breadcrumb,
  versions,
  activeFilePath,
  onSelectVersion,
  onUpload,
  onRegenerate,
  isRegenerating,
}: SectionDetailProps) {
  const [headings, setHeadings] = useState<Heading[]>([]);
  const [activeHeading, setActiveHeading] = useState<string>('');
  const [copied, setCopied] = useState(false);
  const [activeView, setActiveView] = useState<'structured' | 'raw'>('structured');
  const contentRef = useRef<HTMLDivElement>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);

  const handleHeadingsReady = useCallback((h: Heading[]) => {
    setHeadings(h);
    if (h.length > 0 && !activeHeading) setActiveHeading(h[0].id);
  }, [activeHeading]);

  useEffect(() => {
    if (headings.length === 0) return;
    if (observerRef.current) observerRef.current.disconnect();
    const observer = new IntersectionObserver(
      (entries) => { for (const e of entries) { if (e.isIntersecting) setActiveHeading(e.target.id); } },
      { rootMargin: '-20% 0px -80% 0px' }
    );
    observerRef.current = observer;
    const timer = setTimeout(() => {
      for (const h of headings.filter(h => h.level === 2)) {
        const el = document.getElementById(h.id);
        if (el) observer.observe(el);
      }
    }, 200);
    return () => { clearTimeout(timer); observer.disconnect(); };
  }, [headings]);

  const scrollTo = (id: string) => {
    setActiveHeading(id);
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const h2Headings = headings.filter(h => h.level === 2);

  return (
    <div>
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 mb-4 text-[12px]">
        {breadcrumb.map((crumb, i) => (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && <ChevronRight size={11} strokeWidth={1.5} className="text-text-tertiary" />}
            {i < breadcrumb.length - 1 ? (
              <button onClick={onBack} className="text-text-secondary hover:text-accent cursor-pointer transition-colors">
                {crumb}
              </button>
            ) : (
              <span className="text-text-primary font-medium">{crumb}</span>
            )}
          </span>
        ))}
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="font-display text-[20px] font-semibold tracking-[-0.02em] text-text-primary">
              {title}
            </h1>
            <Badge variant="info">{version}</Badge>
          </div>
          <div className="flex items-center gap-3 text-[12px] text-text-tertiary">
            <span className="flex items-center gap-1"><Clock size={11} strokeWidth={1.5} />Updated {lastUpdated}</span>
            <span>&middot;</span>
            <span>by {createdBy}</span>
            <span>&middot;</span>
            <span>{wordCount.toLocaleString()} words</span>
          </div>
          {tags.length > 0 && (
            <div className="flex items-center gap-1.5 mt-2">
              {tags.map((tag, i) => (
                <span key={tag} className={`inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-sm border ${TAG_COLORS[i % TAG_COLORS.length]}`}>
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Structured / Raw toggle */}
          <div className="inline-flex border border-border rounded-sm overflow-hidden mr-1">
            <button
              onClick={() => setActiveView('structured')}
              className={`px-3 py-1.5 text-[12px] font-medium transition-colors cursor-pointer ${
                activeView === 'structured' ? 'bg-accent text-text-on-accent' : 'bg-surface text-text-secondary hover:text-text-primary'
              }`}
            >
              Structured
            </button>
            <button
              onClick={() => setActiveView('raw')}
              className={`px-3 py-1.5 text-[12px] font-medium transition-colors cursor-pointer ${
                activeView === 'raw' ? 'bg-accent text-text-on-accent' : 'bg-surface text-text-secondary hover:text-text-primary'
              }`}
            >
              Raw Document
            </button>
          </div>
          <Button variant="secondary" onClick={handleCopy}>
            {copied ? <Check size={13} strokeWidth={1.5} className="mr-1" /> : <Copy size={13} strokeWidth={1.5} className="mr-1" />}
            {copied ? 'Copied' : 'Copy'}
          </Button>
          <Button variant="secondary">
            <Edit3 size={13} strokeWidth={1.5} className="mr-1" />
            Edit
          </Button>
          <Button variant="secondary">
            <Upload size={13} strokeWidth={1.5} className="mr-1" />
            Replace
          </Button>
          <Button variant="secondary">
            <Download size={13} strokeWidth={1.5} className="mr-1" />
            Download
          </Button>
          <Button
            variant="secondary"
            onClick={onRegenerate}
            disabled={isRegenerating}
          >
            {isRegenerating ? (
              <Loader2 size={13} strokeWidth={1.5} className="mr-1 animate-spin" />
            ) : (
              <RefreshCw size={13} strokeWidth={1.5} className="mr-1" />
            )}
            {isRegenerating ? 'Regenerating...' : 'Re-generate'}
          </Button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex gap-5 h-[calc(100vh-280px)]">
        {/* Content */}
        <div className="flex-1 overflow-y-auto border border-border rounded-md bg-surface" ref={contentRef}>
          <div className="px-8 py-5">
            <MarkdownRenderer content={markdown} onHeadingsReady={handleHeadingsReady} />
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="w-[200px] flex-shrink-0 space-y-4 overflow-y-auto max-h-[calc(100vh-280px)]">
          {/* TOC */}
          {h2Headings.length > 0 && (
            <div className="border border-border rounded-md bg-surface p-4">
              <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary mb-3">On this page</div>
              <nav className="space-y-0.5">
                {h2Headings.map(h => (
                  <button
                    key={h.id}
                    onClick={() => scrollTo(h.id)}
                    className={`block w-full text-left px-2.5 py-1.5 text-[12px] rounded-md transition-colors cursor-pointer ${
                      activeHeading === h.id
                        ? 'text-accent font-medium bg-accent-subtle'
                        : 'text-text-secondary hover:text-text-primary hover:bg-bg'
                    }`}
                  >
                    {h.text}
                  </button>
                ))}
              </nav>
            </div>
          )}

          {/* Version History */}
          {versions && versions.length > 0 && onSelectVersion ? (
            <VersionHistory versions={versions} activeFilePath={activeFilePath} onSelectVersion={onSelectVersion} />
          ) : (
            <div className="border border-border rounded-md bg-surface p-4">
              <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary mb-3">Version History</div>
              <div className="px-2.5 py-2 rounded-md bg-accent-subtle border border-accent/20 text-[12px]">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-text-primary">{version}</span>
                  <Badge variant="info" className="!text-[8px] !h-[16px]">Current</Badge>
                </div>
                <div className="text-[11px] text-text-tertiary mt-0.5">{lastUpdated} &middot; {createdBy}</div>
              </div>
            </div>
          )}

          {/* Upload */}
          <div
            onClick={onUpload}
            className="border-2 border-dashed border-border rounded-md p-4 text-center hover:border-border-strong transition-colors cursor-pointer"
          >
            <Upload size={18} strokeWidth={1.5} className="text-text-tertiary mx-auto mb-1.5" />
            <p className="text-[11px] font-medium text-text-secondary">Upload replacement</p>
            <p className="text-[10px] text-text-tertiary">.md, .txt, .pdf</p>
          </div>
        </div>
      </div>
    </div>
  );
}
