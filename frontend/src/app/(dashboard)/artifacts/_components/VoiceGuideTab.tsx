'use client';

import { useState } from 'react';
import { Badge } from '@/components/ui';
import { ChevronDown, ChevronRight, Check } from 'lucide-react';
import { MarkdownRenderer } from './MarkdownRenderer';

interface VoiceGuideTabProps {
  markdown: string;
  registers: { name: string; sentenceLength: string; paragraphLength: string; tone: string; pace: string }[];
  lexicon: {
    favor: { term: string; usage: string; frequency: string }[];
    avoid: { term: string; usage: string; frequency: string }[];
  };
  antiPatterns: string[];
  workedExamples: { title: string; before: string; after: string; explanation: string }[];
}

export function VoiceGuideTab({ markdown, registers, lexicon, antiPatterns, workedExamples }: VoiceGuideTabProps) {
  const [activeRegister, setActiveRegister] = useState<string>('tactical');
  const [expandedExamples, setExpandedExamples] = useState<Set<number>>(new Set());
  const [checkedAntiPatterns, setCheckedAntiPatterns] = useState<Set<number>>(new Set());

  const currentRegister = registers.find(r => r.name === activeRegister) || registers[0];

  const toggleExample = (idx: number) => {
    setExpandedExamples(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const toggleAntiPattern = (idx: number) => {
    setCheckedAntiPatterns(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      {/* Register Selector */}
      <div>
        <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
          Voice Register
        </div>
        <div className="inline-flex border border-border rounded-sm overflow-hidden">
          {registers.map(r => (
            <button
              key={r.name}
              onClick={() => setActiveRegister(r.name)}
              className={`px-3 py-1.5 text-[11px] font-medium capitalize transition-colors cursor-pointer ${
                activeRegister === r.name
                  ? 'bg-accent text-text-on-accent'
                  : 'bg-surface text-text-secondary hover:text-text-primary'
              }`}
            >
              {r.name}
            </button>
          ))}
        </div>

        {/* Register Metrics */}
        {currentRegister && (
          <div className="grid grid-cols-4 gap-3 mt-3">
            <div className="bg-surface border border-border rounded-md p-3">
              <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">Sentence Length</div>
              <div className="text-[14px] font-semibold text-text-primary">{currentRegister.sentenceLength}</div>
            </div>
            <div className="bg-surface border border-border rounded-md p-3">
              <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">Paragraph Length</div>
              <div className="text-[14px] font-semibold text-text-primary">{currentRegister.paragraphLength}</div>
            </div>
            <div className="bg-surface border border-border rounded-md p-3">
              <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">Tone</div>
              <div className="text-[14px] font-semibold text-text-primary">{currentRegister.tone}</div>
            </div>
            <div className="bg-surface border border-border rounded-md p-3">
              <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">Pace</div>
              <div className="text-[14px] font-semibold text-text-primary">{currentRegister.pace}</div>
            </div>
          </div>
        )}
      </div>

      {/* Lexicon Browser */}
      <div>
        <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
          Lexicon
        </div>
        <div className="grid grid-cols-2 gap-4">
          {/* Favor */}
          <div className="bg-surface border border-border rounded-md p-4">
            <div className="flex items-center gap-2 mb-3">
              <Badge variant="success">FAVOR</Badge>
              <span className="text-[10px] text-text-tertiary">{lexicon.favor.length} terms</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {lexicon.favor.map(item => (
                <span
                  key={item.term}
                  className="inline-flex items-center px-2 py-1 text-[11px] font-mono bg-success-subtle text-success border border-success/20 rounded-sm cursor-default"
                  title={`${item.usage} — ${item.frequency}`}
                >
                  {item.term}
                </span>
              ))}
            </div>
          </div>

          {/* Avoid */}
          <div className="bg-surface border border-border rounded-md p-4">
            <div className="flex items-center gap-2 mb-3">
              <Badge variant="error">AVOID</Badge>
              <span className="text-[10px] text-text-tertiary">{lexicon.avoid.length} terms</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {lexicon.avoid.map(item => (
                <span
                  key={item.term}
                  className="inline-flex items-center px-2 py-1 text-[11px] font-mono bg-error-subtle text-error border border-error/20 rounded-sm cursor-default line-through"
                  title={`${item.usage}`}
                >
                  {item.term}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Anti-Pattern Checklist */}
      <div>
        <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
          Anti-Pattern Checklist
        </div>
        <div className="bg-surface border border-border rounded-md p-4 space-y-2">
          {antiPatterns.map((pattern, idx) => (
            <label
              key={idx}
              className="flex items-start gap-2 cursor-pointer group"
              onClick={() => toggleAntiPattern(idx)}
            >
              <div className={`w-4 h-4 mt-0.5 rounded-sm border flex-shrink-0 flex items-center justify-center transition-colors ${
                checkedAntiPatterns.has(idx)
                  ? 'bg-accent border-accent'
                  : 'border-border group-hover:border-border-strong'
              }`}>
                {checkedAntiPatterns.has(idx) && <Check size={10} strokeWidth={2} className="text-text-on-accent" />}
              </div>
              <span className={`text-[12px] leading-[1.55] ${
                checkedAntiPatterns.has(idx) ? 'text-text-tertiary line-through' : 'text-text-secondary'
              }`}>
                {pattern}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Before/After Examples */}
      <div>
        <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
          Before / After Examples
        </div>
        <div className="space-y-2">
          {workedExamples.map((example, idx) => (
            <div key={idx} className="bg-surface border border-border rounded-md overflow-hidden">
              <button
                onClick={() => toggleExample(idx)}
                className="w-full flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-bg transition-colors"
              >
                <span className="text-[13px] font-medium text-text-primary">{example.title}</span>
                {expandedExamples.has(idx) ? (
                  <ChevronDown size={14} strokeWidth={1.5} className="text-text-tertiary" />
                ) : (
                  <ChevronRight size={14} strokeWidth={1.5} className="text-text-tertiary" />
                )}
              </button>
              {expandedExamples.has(idx) && (
                <div className="px-4 pb-4 space-y-3">
                  {/* Before */}
                  <div>
                    <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-error mb-1">Before</div>
                    <div className="bg-bg border border-border rounded-md p-3">
                      <p className="text-[12px] text-text-secondary leading-[1.55] italic">{example.before}</p>
                    </div>
                  </div>
                  {/* After */}
                  <div>
                    <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-success mb-1">After</div>
                    <div className="bg-accent-subtle border border-accent/20 rounded-md p-3">
                      <p className="text-[12px] text-text-secondary leading-[1.55]">{example.after}</p>
                    </div>
                  </div>
                  {/* Explanation */}
                  <div className="text-[11px] text-text-tertiary leading-[1.5]">
                    {example.explanation}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Full Guide Markdown */}
      <div>
        <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
          Full Guide
        </div>
        <div className="bg-surface border border-border rounded-md p-6">
          <MarkdownRenderer content={markdown} />
        </div>
      </div>
    </div>
  );
}
