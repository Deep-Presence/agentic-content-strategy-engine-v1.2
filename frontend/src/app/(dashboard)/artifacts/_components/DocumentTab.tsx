'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { Badge } from '@/components/ui';
import { Search, Copy, Check } from 'lucide-react';
import type { KBDocument } from '@/types';
import { MarkdownRenderer } from './MarkdownRenderer';

const TYPE_LABELS: Record<string, string> = {
  company_overview: 'Company Overview',
  brand_perception: 'Brand Perception',
  competitor_registry: 'Competitor Registry',
  customer_reviews: 'Customer Reviews',
  weakness_analysis: 'Weakness Analysis',
};

interface DocumentTabProps {
  doc: KBDocument;
}

interface Heading {
  id: string;
  text: string;
  level: number;
}

export function DocumentTab({ doc }: DocumentTabProps) {
  const [headings, setHeadings] = useState<Heading[]>([]);
  const [activeHeading, setActiveHeading] = useState<string>('');
  const [search, setSearch] = useState('');
  const [copied, setCopied] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);

  const handleHeadingsReady = useCallback((h: Heading[]) => {
    setHeadings(h);
    if (h.length > 0 && !activeHeading) {
      setActiveHeading(h[0].id);
    }
  }, [activeHeading]);

  // IntersectionObserver for scroll-tracking active section
  useEffect(() => {
    if (headings.length === 0) return;

    // Disconnect previous observer
    if (observerRef.current) {
      observerRef.current.disconnect();
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveHeading(entry.target.id);
          }
        }
      },
      { rootMargin: '-20% 0px -80% 0px' }
    );

    observerRef.current = observer;

    // Delay to let markdown render heading elements
    const timer = setTimeout(() => {
      const h2s = headings.filter(h => h.level === 2);
      for (const heading of h2s) {
        const el = document.getElementById(heading.id);
        if (el) observer.observe(el);
      }
    }, 200);

    return () => {
      clearTimeout(timer);
      observer.disconnect();
    };
  }, [headings]);

  const scrollTo = (id: string) => {
    setActiveHeading(id);
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(doc.markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const h2Headings = headings.filter(h => h.level === 2);

  const lastUpdated = new Date(doc.lastUpdated).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <div>
      {/* Metadata Bar */}
      <div className="flex items-center gap-2 mb-4 pb-3 border-b border-border">
        <Badge variant="info">{TYPE_LABELS[doc.type] || doc.type}</Badge>
        <Badge variant="neutral">{doc.client}</Badge>
        <Badge variant="neutral">{doc.version}</Badge>
        <span className="text-[11px] text-text-tertiary">{doc.wordCount.toLocaleString()} words</span>
        <span className="text-[10px] text-text-tertiary ml-auto">Last updated: {lastUpdated}</span>
      </div>

      {/* 2-Column Layout */}
      <div className="flex gap-0 h-[calc(100vh-220px)]">
        {/* Left: Section Nav */}
        <div className="w-[200px] flex-shrink-0 border-r border-border overflow-y-auto">
          <div className="p-3">
            <h2 className="text-[14px] font-semibold text-text-primary mb-1">
              {TYPE_LABELS[doc.type] || doc.type}
            </h2>
            <div className="text-[10px] text-text-tertiary mb-3">
              Updated {lastUpdated}
            </div>

            <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
              Sections
            </div>
            <nav className="space-y-0.5 mb-4">
              {h2Headings.map(h => (
                <button
                  key={h.id}
                  onClick={() => scrollTo(h.id)}
                  className={`block w-full text-left px-2 py-1.5 text-[11px] rounded-sm transition-colors cursor-pointer border-l-2 ${
                    activeHeading === h.id
                      ? 'border-accent text-accent font-medium bg-accent-subtle'
                      : 'border-transparent text-text-secondary hover:text-text-primary hover:bg-bg'
                  }`}
                >
                  {h.text}
                </button>
              ))}
            </nav>

            <div className="text-[10px] text-text-tertiary mb-3">
              {doc.wordCount.toLocaleString()} words
            </div>

            {/* Export */}
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 h-[26px] px-2 text-[11px] w-full border border-border rounded-sm text-text-secondary hover:border-border-strong cursor-pointer transition-colors"
            >
              {copied ? <Check size={12} strokeWidth={1.5} className="text-success" /> : <Copy size={12} strokeWidth={1.5} />}
              {copied ? 'Copied!' : 'Copy to Clipboard'}
            </button>
          </div>
        </div>

        {/* Right: Content */}
        <div className="flex-1 overflow-y-auto" ref={contentRef}>
          <div className="px-6 py-4">
            {/* Search */}
            <div className="flex items-center justify-end mb-4">
              <div className="relative">
                <Search size={12} strokeWidth={1.5} className="absolute left-2 top-1/2 -translate-y-1/2 text-text-tertiary" />
                <input
                  type="text"
                  placeholder="Search document..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="h-[26px] pl-7 pr-2 text-[11px] border border-border rounded-sm bg-surface text-text-primary outline-none focus:border-accent w-[200px]"
                />
              </div>
            </div>

            {/* Markdown Content */}
            <MarkdownRenderer
              content={doc.markdown}
              onHeadingsReady={handleHeadingsReady}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
