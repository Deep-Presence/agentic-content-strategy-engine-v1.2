'use client';

import { useState } from 'react';
import { Card, Badge, Button } from '@/components/ui';
import {
  ChevronDown,
  ChevronRight,
  Check,
  RefreshCw,
  Download,
  Upload,
  Clock,
  Mic,
  Copy,
  ArrowRight,
  AlertCircle,
  Edit3,
} from 'lucide-react';
import type { VoiceGuide } from '@/types';
import { MarkdownRenderer } from './MarkdownRenderer';

interface VoiceGuideViewProps {
  voiceGuide: VoiceGuide;
  markdown: string;
  onBack: () => void;
}

export function VoiceGuideView({ voiceGuide, markdown, onBack }: VoiceGuideViewProps) {
  const [activeRegister, setActiveRegister] = useState<string>(
    voiceGuide.registers[0]?.name || 'tactical'
  );
  const [expandedExamples, setExpandedExamples] = useState<Set<number>>(new Set([0]));
  const [checkedAntiPatterns, setCheckedAntiPatterns] = useState<Set<number>>(new Set());
  const [activeView, setActiveView] = useState<'structured' | 'raw'>('structured');

  const currentRegister = voiceGuide.registers.find(r => r.name === activeRegister) || voiceGuide.registers[0];

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
    <div>
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 mb-4 text-[12px]">
        <button onClick={onBack} className="text-text-secondary hover:text-accent cursor-pointer transition-colors">
          Brand Artifact
        </button>
        <ChevronRight size={11} strokeWidth={1.5} className="text-text-tertiary" />
        <span className="text-text-primary font-medium">Brand Voice</span>
      </nav>

      {/* Section Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-md bg-accent-subtle flex items-center justify-center">
            <Mic size={18} strokeWidth={1.5} className="text-accent" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-display text-[16px] font-semibold tracking-[-0.01em] text-text-primary">
                Brand Voice Guide
              </h2>
              <Badge variant="info">v1.0</Badge>
            </div>
            <div className="flex items-center gap-3 mt-0.5 text-[12px] text-text-tertiary">
              <span className="flex items-center gap-1">
                <Clock size={11} strokeWidth={1.5} />
                Updated Mar 24, 2026
              </span>
              <span>&middot;</span>
              <span>by Pipeline AI</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="inline-flex border border-border rounded-sm overflow-hidden">
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
          <Button variant="secondary">
            <Edit3 size={13} strokeWidth={1.5} className="mr-1.5" />
            Edit
          </Button>
          <Button variant="secondary">
            <Upload size={13} strokeWidth={1.5} className="mr-1.5" />
            Replace
          </Button>
          <Button variant="secondary">
            <Download size={13} strokeWidth={1.5} className="mr-1.5" />
            Download
          </Button>
          <Button variant="secondary">
            <RefreshCw size={13} strokeWidth={1.5} className="mr-1.5" />
            Re-generate
          </Button>
        </div>
      </div>

      <div className="flex gap-5">
        {/* Main Content */}
        <div className="flex-1 max-h-[calc(100vh-280px)] overflow-y-auto">
      {activeView === 'raw' ? (
        <Card className="!p-6">
          <MarkdownRenderer content={markdown} />
        </Card>
      ) : (
        <div className="space-y-5">
          {/* Voice Identity — Hero Card */}
          {voiceGuide.identity && (
            <Card className="!p-5 bg-accent-subtle/30 border-accent/20">
              <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-accent mb-3">
                Voice Identity
              </div>
              <p className="text-[15px] text-text-primary leading-[1.7] font-body">
                {voiceGuide.identity.split('\n')[0]}
              </p>
              {voiceGuide.identity.split('\n').length > 1 && (
                <div className="mt-3 pt-3 border-t border-accent/10">
                  {voiceGuide.identity.split('\n').slice(1).filter(l => l.trim()).map((line, i) => {
                    const cleaned = line.replace(/^[-*]\s*/, '').replace(/\*\*/g, '');
                    if (!cleaned) return null;
                    const colonIdx = cleaned.indexOf(':');
                    if (colonIdx > 0 && colonIdx < 30) {
                      return (
                        <div key={i} className="flex items-start gap-2 py-1.5">
                          <div className="w-2 h-2 rounded-full bg-accent mt-2 flex-shrink-0" />
                          <p className="text-[13px] leading-[1.6]">
                            <span className="font-semibold text-text-primary">{cleaned.slice(0, colonIdx)}</span>
                            <span className="text-text-secondary">{cleaned.slice(colonIdx)}</span>
                          </p>
                        </div>
                      );
                    }
                    return (
                      <div key={i} className="flex items-start gap-2 py-1">
                        <div className="w-2 h-2 rounded-full bg-accent mt-2 flex-shrink-0" />
                        <p className="text-[13px] text-text-secondary leading-[1.6]">{cleaned}</p>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>
          )}

          {/* Voice Registers */}
          <Card className="!p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary">
                Voice Registers
              </div>
              <div className="text-[12px] text-text-tertiary">
                Select a register to see its parameters
              </div>
            </div>

            {/* Register Tabs */}
            <div className="flex gap-2 mb-4">
              {voiceGuide.registers.map(r => (
                <button
                  key={r.name}
                  onClick={() => setActiveRegister(r.name)}
                  className={`px-4 py-2 text-[13px] font-medium capitalize rounded-md transition-all cursor-pointer border ${
                    activeRegister === r.name
                      ? 'bg-accent text-text-on-accent border-accent'
                      : 'bg-surface text-text-secondary border-border hover:border-border-strong hover:text-text-primary'
                  }`}
                >
                  {r.name}
                </button>
              ))}
            </div>

            {/* Register Metrics */}
            {currentRegister && (
              <div className="grid grid-cols-4 gap-3">
                {[
                  { label: 'Sentence Length', value: currentRegister.sentenceLength, desc: 'Average words per sentence' },
                  { label: 'Paragraph Length', value: currentRegister.paragraphLength, desc: 'Sentences per paragraph' },
                  { label: 'Tone', value: currentRegister.tone, desc: 'Communication style' },
                  { label: 'Pace', value: currentRegister.pace, desc: 'Reading speed target' },
                ].map(metric => (
                  <div key={metric.label} className="bg-bg border border-border rounded-md p-4">
                    <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary mb-2">
                      {metric.label}
                    </div>
                    <div className="text-[16px] font-semibold text-text-primary mb-0.5">
                      {metric.value}
                    </div>
                    <div className="text-[11px] text-text-tertiary">{metric.desc}</div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Lexicon — Side by side */}
          <div className="grid grid-cols-2 gap-4">
            {/* Favor Terms */}
            <Card className="!p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-success" />
                  <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary">Preferred Terms</span>
                </div>
                <Badge variant="success">{voiceGuide.lexicon.favor.length} terms</Badge>
              </div>
              <div className="space-y-2">
                {voiceGuide.lexicon.favor.map(item => (
                  <div
                    key={item.term}
                    className="flex items-start gap-3 px-3 py-2.5 bg-success-subtle/50 border border-success/10 rounded-md"
                  >
                    <code className="text-[13px] font-mono font-semibold text-success flex-shrink-0">
                      {item.term}
                    </code>
                    <span className="text-[12px] text-text-secondary leading-[1.5]">
                      {item.usage}
                    </span>
                    <Badge variant="neutral" className="ml-auto flex-shrink-0 !text-[9px]">
                      {item.frequency}
                    </Badge>
                  </div>
                ))}
              </div>
            </Card>

            {/* Avoid Terms */}
            <Card className="!p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-error" />
                  <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary">Terms to Avoid</span>
                </div>
                <Badge variant="error">{voiceGuide.lexicon.avoid.length} terms</Badge>
              </div>
              <div className="space-y-2">
                {voiceGuide.lexicon.avoid.map(item => (
                  <div
                    key={item.term}
                    className="flex items-center gap-3 px-3 py-2.5 bg-error-subtle/50 border border-error/10 rounded-md"
                  >
                    <code className="text-[13px] font-mono font-semibold text-error line-through flex-shrink-0">
                      {item.term}
                    </code>
                    <ArrowRight size={12} strokeWidth={1.5} className="text-text-tertiary flex-shrink-0" />
                    <span className="text-[12px] text-text-secondary leading-[1.5]">
                      {item.usage}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* Anti-Patterns */}
          {voiceGuide.antiPatterns.length > 0 && (
            <Card className="!p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <AlertCircle size={14} strokeWidth={1.5} className="text-warning" />
                  <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary">
                    Content Quality Checklist
                  </span>
                </div>
                <span className="text-[12px] text-text-tertiary">
                  {checkedAntiPatterns.size}/{voiceGuide.antiPatterns.length} reviewed
                </span>
              </div>
              <div className="space-y-1">
                {voiceGuide.antiPatterns.map((pattern, idx) => {
                  const dashIdx = pattern.indexOf(' — ');
                  const title = dashIdx > 0 ? pattern.slice(0, dashIdx) : pattern;
                  const desc = dashIdx > 0 ? pattern.slice(dashIdx + 3) : '';

                  return (
                    <button
                      key={idx}
                      onClick={() => toggleAntiPattern(idx)}
                      className={`w-full flex items-start gap-3 px-3 py-3 rounded-md text-left cursor-pointer transition-colors ${
                        checkedAntiPatterns.has(idx)
                          ? 'bg-success-subtle/30'
                          : 'hover:bg-bg'
                      }`}
                    >
                      <div className={`w-5 h-5 mt-0.5 rounded-sm border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
                        checkedAntiPatterns.has(idx) ? 'bg-success border-success' : 'border-border'
                      }`}>
                        {checkedAntiPatterns.has(idx) && <Check size={12} strokeWidth={2.5} className="text-white" />}
                      </div>
                      <div className="min-w-0">
                        <div className={`text-[13px] font-medium leading-[1.5] ${
                          checkedAntiPatterns.has(idx) ? 'text-text-tertiary line-through' : 'text-text-primary'
                        }`}>
                          {title}
                        </div>
                        {desc && (
                          <div className={`text-[12px] leading-[1.5] mt-0.5 ${
                            checkedAntiPatterns.has(idx) ? 'text-text-tertiary' : 'text-text-secondary'
                          }`}>
                            {desc}
                          </div>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </Card>
          )}

          {/* Before/After Examples */}
          {voiceGuide.workedExamples.length > 0 && (
            <Card className="!p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Copy size={14} strokeWidth={1.5} className="text-accent" />
                  <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary">
                    Writing Examples
                  </span>
                </div>
                <span className="text-[12px] text-text-tertiary">
                  {voiceGuide.workedExamples.length} examples
                </span>
              </div>
              <div className="space-y-3">
                {voiceGuide.workedExamples.map((example, idx) => (
                  <div key={idx} className="border border-border rounded-md overflow-hidden">
                    <button
                      onClick={() => toggleExample(idx)}
                      className="w-full flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-bg transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-[13px] font-medium text-text-primary">{example.title}</span>
                      </div>
                      {expandedExamples.has(idx) ? (
                        <ChevronDown size={15} strokeWidth={1.5} className="text-text-tertiary" />
                      ) : (
                        <ChevronRight size={15} strokeWidth={1.5} className="text-text-tertiary" />
                      )}
                    </button>

                    {expandedExamples.has(idx) && (
                      <div className="px-4 pb-4 border-t border-border pt-3">
                        <div className="grid grid-cols-2 gap-3 mb-3">
                          {/* Before */}
                          <div>
                            <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-error mb-2 flex items-center gap-1.5">
                              <div className="w-2 h-2 rounded-full bg-error" />
                              Before
                            </div>
                            <div className="bg-error-subtle/30 border border-error/10 rounded-md p-4">
                              <p className="text-[13px] text-text-secondary leading-[1.7] italic">
                                {example.before}
                              </p>
                            </div>
                          </div>
                          {/* After */}
                          <div>
                            <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-success mb-2 flex items-center gap-1.5">
                              <div className="w-2 h-2 rounded-full bg-success" />
                              After
                            </div>
                            <div className="bg-success-subtle/30 border border-success/10 rounded-md p-4">
                              <p className="text-[13px] text-text-primary leading-[1.7]">
                                {example.after}
                              </p>
                            </div>
                          </div>
                        </div>
                        {/* Explanation */}
                        <div className="bg-bg border border-border rounded-md px-4 py-3">
                          <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary mb-1.5">
                            What Changed
                          </div>
                          <p className="text-[13px] text-text-secondary leading-[1.6]">
                            {example.explanation}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
        </div>

        {/* Right sidebar: Version History + Upload */}
        <div className="w-[200px] flex-shrink-0 space-y-4">
          {/* Version History */}
          <div className="border border-border rounded-md bg-surface p-4">
            <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary mb-3">Version History</div>
            <div className="space-y-2">
              <div className="px-2.5 py-2 rounded-md bg-accent-subtle border border-accent/20 text-[12px]">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-text-primary">v1.0</span>
                  <Badge variant="info" className="!text-[8px] !h-[16px]">Current</Badge>
                </div>
                <div className="text-[11px] text-text-tertiary mt-0.5">Mar 24, 2026 &middot; Pipeline AI</div>
              </div>
            </div>
            <button className="w-full mt-2 px-2.5 py-2 text-[12px] text-accent hover:bg-accent-subtle rounded-md transition-colors cursor-pointer text-center">
              + Create New Version
            </button>
          </div>

          {/* Upload replacement */}
          <div className="border-2 border-dashed border-border rounded-md p-4 text-center hover:border-border-strong transition-colors cursor-pointer">
            <Upload size={18} strokeWidth={1.5} className="text-text-tertiary mx-auto mb-1.5" />
            <p className="text-[11px] font-medium text-text-secondary">Upload replacement</p>
            <p className="text-[10px] text-text-tertiary">.md, .txt, .pdf</p>
          </div>
        </div>
      </div>
    </div>
  );
}
