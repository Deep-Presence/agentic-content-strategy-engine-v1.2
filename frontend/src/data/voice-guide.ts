import type { VoiceGuide, LexiconItem } from '@/types';
import fs from 'fs';
import path from 'path';

function parseFavorTerms(content: string): LexiconItem[] {
  const favorMatch = content.match(/\*\*FAVOR\*\*\n([\s\S]*?)(?=\n\*\*AVOID\*\*)/);
  if (!favorMatch) return [];
  const lines = favorMatch[1].split('\n').filter(l => l.startsWith('- `'));
  return lines.map(line => {
    const termMatch = line.match(/^- `([^`]+)`\s*—\s*(.*?)\s*—\s*(.*)/);
    if (termMatch) {
      return { term: termMatch[1], usage: termMatch[2].trim(), frequency: termMatch[3].trim() };
    }
    const simpleMatch = line.match(/^- `([^`]+)`\s*—\s*(.*)/);
    if (simpleMatch) {
      return { term: simpleMatch[1], usage: simpleMatch[2].trim(), frequency: '' };
    }
    return { term: line.replace(/^- `|`.*$/g, ''), usage: '', frequency: '' };
  });
}

function parseAvoidTerms(content: string): LexiconItem[] {
  const avoidMatch = content.match(/\*\*AVOID\*\*\n([\s\S]*?)(?=\n\*\*DOMAIN TERMS\*\*|\n---|\n##)/);
  if (!avoidMatch) return [];
  const lines = avoidMatch[1].split('\n').filter(l => l.startsWith('- `'));
  return lines.map(line => {
    const termMatch = line.match(/^- `([^`]+)`(?:\s*\(([^)]*)\))?\s*→\s*(.*)/);
    if (termMatch) {
      return { term: termMatch[1], usage: termMatch[3].trim(), frequency: termMatch[2] || '' };
    }
    return { term: line.replace(/^- `|`.*$/g, ''), usage: '', frequency: '' };
  });
}

function parseAntiPatterns(content: string): string[] {
  const section = content.match(/\*\*NEVER DO THESE\*\*\n\n([\s\S]*?)(?=\n\*\*QUICK DRIFT CHECK\*\*|\n---|\n##)/);
  if (!section) return [];
  return section[1]
    .split('\n')
    .filter(l => /^\d+\./.test(l.trim()))
    .map(l => l.replace(/^\d+\.\s*/, '').replace(/\*\*/g, '').trim());
}

function parseWorkedExamples(content: string): { title: string; before: string; after: string; explanation: string }[] {
  const examples: { title: string; before: string; after: string; explanation: string }[] = [];

  // Parse Before/After pairs
  const baSection = content.match(/### B\. Before\/After Pairs([\s\S]*?)(?=### C\.|## Section|$)/);
  if (baSection) {
    const pairs = baSection[1].split(/\*\*Before\/After #\d+:/);
    for (const pair of pairs.slice(1)) {
      const titleMatch = pair.match(/^([^*]+)\*\*/);
      const beforeMatch = pair.match(/BEFORE[^>]*>\s*([\s\S]*?)(?=\nAFTER)/);
      const afterMatch = pair.match(/AFTER[^>]*>\s*([\s\S]*?)(?=\n\*What changed)/);
      const explanationMatch = pair.match(/\*What changed:\s*([\s\S]*?)\*/);

      if (titleMatch) {
        examples.push({
          title: titleMatch[1].trim(),
          before: beforeMatch ? beforeMatch[1].replace(/^>\s*/gm, '').trim() : '',
          after: afterMatch ? afterMatch[1].replace(/^>\s*/gm, '').trim() : '',
          explanation: explanationMatch ? explanationMatch[1].trim() : '',
        });
      }
    }
  }

  return examples;
}

export function getVoiceGuide(): VoiceGuide | null {
  const mdPath = path.join(process.cwd(), 'data/artifacts/voice_style_guide/lovable/guide/v1.md');

  try {
    const content = fs.readFileSync(mdPath, 'utf-8');

    return {
      identity: content.match(/## Section 1: Voice Identity\n\n([\s\S]*?)(?=\n---)/)?.[1]?.trim() || content.slice(0, 500),
      registers: [
        { name: 'tactical', sentenceLength: '9-14 words', paragraphLength: '2-3 sentences', tone: 'Direct', pace: '8/10' },
        { name: 'analytical', sentenceLength: '15-22 words', paragraphLength: '3-5 sentences', tone: 'Rigorous', pace: '6/10' },
        { name: 'empathy', sentenceLength: '11-16 words', paragraphLength: '2-4 sentences', tone: 'Validating', pace: '7/10' },
      ],
      styleMetrics: {},
      lexicon: {
        favor: parseFavorTerms(content),
        avoid: parseAvoidTerms(content),
      },
      antiPatterns: parseAntiPatterns(content),
      workedExamples: parseWorkedExamples(content),
    };
  } catch {
    return null;
  }
}

export function getVoiceGuideMarkdown(): string {
  const mdPath = path.join(process.cwd(), 'data/artifacts/voice_style_guide/lovable/guide/v1.md');
  try {
    return fs.readFileSync(mdPath, 'utf-8');
  } catch {
    return '';
  }
}
