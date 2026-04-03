'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import { Card, Badge, Button } from '@/components/ui';
import {
  ChevronRight,
  Edit3,
  RefreshCw,
  Download,
  Clock,
  Check,
  Upload,
} from 'lucide-react';
import type { Persona } from '@/types';
import { VersionHistory } from './VersionHistory';
import type { VersionEntry } from '../_lib/types';

interface PersonaDetailProps {
  persona: Persona;
  onBack: () => void;
  versions?: VersionEntry[];
  activeFilePath?: string;
  onSelectVersion?: (entry: VersionEntry) => void;
  onUpload?: () => void;
}

// Color theme per section type
const SECTION_THEMES: Record<string, { dot: string; bgSubtle: string }> = {
  'pain': { dot: 'bg-error', bgSubtle: 'bg-error-subtle/30' },
  'buying': { dot: 'bg-success', bgSubtle: 'bg-success-subtle/30' },
  'goals': { dot: 'bg-info', bgSubtle: 'bg-info-subtle/30' },
  'success': { dot: 'bg-accent', bgSubtle: 'bg-accent-subtle/30' },
  'messaging': { dot: 'bg-accent', bgSubtle: '' },
  'engagement': { dot: 'bg-warning', bgSubtle: '' },
  'language': { dot: 'bg-info', bgSubtle: '' },
  'default': { dot: 'bg-border-strong', bgSubtle: '' },
};

function getSectionTheme(title: string) {
  const lower = title.toLowerCase();
  for (const [key, theme] of Object.entries(SECTION_THEMES)) {
    if (key !== 'default' && lower.includes(key)) return theme;
  }
  return SECTION_THEMES.default;
}

function ParsedContent({ content, sectionTitle }: { content: string; sectionTitle: string }) {
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  const theme = getSectionTheme(sectionTitle);

  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (!trimmed) continue;

    // H3 subheaders
    if (trimmed.startsWith('### ')) {
      elements.push(
        <h4 key={i} className="text-[14px] font-semibold text-text-primary mt-5 mb-2 first:mt-0">
          {trimmed.replace(/^### /, '').replace(/\*\*/g, '')}
        </h4>
      );
      continue;
    }

    // Bullet with bold key-value ("- **Key:** Value")
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      const bulletContent = trimmed.replace(/^[-*]\s+/, '');
      const boldMatch = bulletContent.match(/^\*\*([^*]+)\*\*[:\s]*(.*)/);

      if (boldMatch) {
        elements.push(
          <div key={i} className="flex items-start gap-3 py-2 px-3 rounded-md hover:bg-bg transition-colors">
            <div className={`w-2 h-2 rounded-full ${theme.dot} mt-2 flex-shrink-0`} />
            <div className="text-[13px] leading-[1.65]">
              <span className="font-semibold text-text-primary">{boldMatch[1]}</span>
              {boldMatch[2] && (
                <span className="text-text-secondary">: {boldMatch[2]}</span>
              )}
            </div>
          </div>
        );
      } else {
        elements.push(
          <div key={i} className="flex items-start gap-3 py-1.5 px-3">
            <div className={`w-2 h-2 rounded-full ${theme.dot} mt-2 flex-shrink-0`} />
            <span className="text-[13px] text-text-secondary leading-[1.65]">
              {bulletContent.replace(/\*\*/g, '')}
            </span>
          </div>
        );
      }
      continue;
    }

    // Numbered items
    if (/^\d+\.\s/.test(trimmed)) {
      const num = trimmed.match(/^(\d+)\.\s*/)?.[1];
      const rest = trimmed.replace(/^\d+\.\s*/, '');
      elements.push(
        <div key={i} className="flex items-start gap-3 py-1.5 px-3">
          <span className="text-[12px] font-mono font-semibold text-accent mt-0.5 flex-shrink-0 w-5 text-right">
            {num}.
          </span>
          <span className="text-[13px] text-text-secondary leading-[1.65]">
            {rest.replace(/\*\*/g, '')}
          </span>
        </div>
      );
      continue;
    }

    // Checkbox items
    if (trimmed.startsWith('- [ ]') || trimmed.startsWith('- [x]')) {
      const isChecked = trimmed.startsWith('- [x]');
      const text = trimmed.replace(/^- \[[ x]\]\s*/, '');
      elements.push(
        <div key={i} className="flex items-start gap-3 py-1.5 px-3">
          <div className={`w-5 h-5 mt-0.5 rounded-sm border-2 flex-shrink-0 flex items-center justify-center ${
            isChecked ? 'bg-success border-success' : 'border-border'
          }`}>
            {isChecked && <Check size={12} strokeWidth={2.5} className="text-white" />}
          </div>
          <span className={`text-[13px] leading-[1.65] ${isChecked ? 'text-text-tertiary line-through' : 'text-text-secondary'}`}>
            {text.replace(/\*\*/g, '')}
          </span>
        </div>
      );
      continue;
    }

    // Quoted text
    if (trimmed.startsWith('"') || trimmed.startsWith('\u201c')) {
      elements.push(
        <div key={i} className="border-l-3 border-accent pl-4 py-2 my-2">
          <p className="text-[13px] text-text-primary leading-[1.7] italic">
            {trimmed.replace(/\*\*/g, '')}
          </p>
        </div>
      );
      continue;
    }

    // Regular paragraph
    elements.push(
      <p key={i} className="text-[13px] text-text-secondary leading-[1.7] mb-2 px-3">
        {trimmed.replace(/\*\*/g, '')}
      </p>
    );
  }

  return <>{elements}</>;
}

export function PersonaDetail({ persona, onBack, versions, activeFilePath, onSelectVersion, onUpload }: PersonaDetailProps) {
  const [activeSection, setActiveSection] = useState<string>('section-0');
  const contentRef = useRef<HTMLDivElement>(null);

  const sectionCount = persona.sections.length;

  const sectionIds = useMemo(
    () => persona.sections.map((s, i) => ({ id: `section-${i}`, title: s.title })),
    [persona.sections]
  );

  // Intersection observer for scroll tracking
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { rootMargin: '-10% 0px -80% 0px' }
    );

    const timer = setTimeout(() => {
      for (let i = 0; i < sectionCount; i++) {
        const el = document.getElementById(`section-${i}`);
        if (el) observer.observe(el);
      }
    }, 100);

    return () => { clearTimeout(timer); observer.disconnect(); };
  }, [persona.id, sectionCount]);

  const scrollTo = (id: string) => {
    setActiveSection(id);
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div>
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 mb-4 text-[12px]">
        <button onClick={onBack} className="text-text-secondary hover:text-accent cursor-pointer transition-colors">
          Brand Artifact
        </button>
        <ChevronRight size={11} strokeWidth={1.5} className="text-text-tertiary" />
        <button onClick={onBack} className="text-text-secondary hover:text-accent cursor-pointer transition-colors">
          Audiences
        </button>
        <ChevronRight size={11} strokeWidth={1.5} className="text-text-tertiary" />
        <span className="text-text-primary font-medium">{persona.name}</span>
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-accent-subtle flex items-center justify-center text-[20px] font-semibold text-accent">
            {persona.name.charAt(0).toUpperCase()}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-display text-[18px] font-semibold tracking-[-0.02em] text-text-primary">
                {persona.name}
              </h2>
              <Badge variant="info">{persona.version}</Badge>
            </div>
            <div className="text-[13px] text-text-secondary mt-0.5">{persona.title}</div>
            <div className="flex items-center gap-3 mt-1 text-[12px] text-text-tertiary">
              <span className="flex items-center gap-1">
                <Clock size={11} strokeWidth={1.5} />
                Generated Mar 24, 2026
              </span>
              <span>&middot;</span>
              <span>by Pipeline AI</span>
              <span>&middot;</span>
              <span>{persona.sections.length} sections</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary">
            <Upload size={13} strokeWidth={1.5} className="mr-1.5" />
            Replace
          </Button>
          <Button variant="secondary">
            <Download size={13} strokeWidth={1.5} className="mr-1.5" />
            Download
          </Button>
          <Button variant="secondary">
            <Edit3 size={13} strokeWidth={1.5} className="mr-1.5" />
            Edit
          </Button>
          <Button variant="secondary">
            <RefreshCw size={13} strokeWidth={1.5} className="mr-1.5" />
            Re-generate
          </Button>
        </div>
      </div>

      {/* 2-Column: Content + TOC */}
      <div className="flex gap-5 h-[calc(100vh-260px)]">
        {/* Main Content */}
        <div className="flex-1 overflow-y-auto rounded-md" ref={contentRef}>
          <div className="space-y-4">
            {persona.sections.map((section, idx) => {
              const theme = getSectionTheme(section.title);
              return (
                <Card
                  key={idx}
                  id={`section-${idx}`}
                  className={`!p-5 ${theme.bgSubtle}`}
                >
                  <h3 className="font-display text-[15px] font-semibold tracking-[-0.01em] text-text-primary mb-3">
                    {section.title.replace(/\*\*/g, '')}
                  </h3>
                  <ParsedContent content={section.content} sectionTitle={section.title} />
                </Card>
              );
            })}
          </div>
        </div>

        {/* Right: TOC + Version + Upload */}
        <div className="w-[200px] flex-shrink-0 space-y-4">
          {/* TOC */}
          <div className="border border-border rounded-md bg-surface p-4 overflow-y-auto">
            <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary mb-3">
              On this page
            </div>
            <nav className="space-y-0.5">
              {sectionIds.map(({ id, title }) => (
                <button
                  key={id}
                  onClick={() => scrollTo(id)}
                  className={`block w-full text-left px-2.5 py-1.5 text-[12px] rounded-md transition-colors cursor-pointer ${
                    activeSection === id
                      ? 'text-accent font-medium bg-accent-subtle'
                      : 'text-text-secondary hover:text-text-primary hover:bg-bg'
                  }`}
                >
                  {title.replace(/\*\*/g, '')}
                </button>
              ))}
            </nav>
          </div>

          {/* Version History */}
          {versions && versions.length > 0 && onSelectVersion ? (
            <VersionHistory versions={versions} activeFilePath={activeFilePath} onSelectVersion={onSelectVersion} />
          ) : (
            <div className="border border-border rounded-md bg-surface p-4">
              <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary mb-3">Version History</div>
              <div className="px-2.5 py-2 rounded-md bg-accent-subtle border border-accent/20 text-[12px]">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-text-primary">{persona.version}</span>
                  <Badge variant="info" className="!text-[8px] !h-[16px]">Current</Badge>
                </div>
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
