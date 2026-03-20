'use client';

import { useState, useEffect, useMemo } from 'react';
import { Skeleton } from '@/components/ui';
import { ArtifactsClient } from './_components/ArtifactsClient';
import { useAuthStore } from '@/stores/auth';
import { apiGet } from '@/lib/api/client';
import { ARTIFACTS } from '@/lib/api/endpoints';
import { useResearchArtifacts, useKBFileList } from '@/lib/hooks/useArtifacts';
import type { KBDocument, Persona, VoiceGuide } from '@/types';

// KB document types stored in artifacts/knowledge_base/{slug}/
const KB_DOC_TYPES = [
  'company_overview',
  'brand_perception',
  'competitor_registry',
  'customer_reviews',
  'weakness_analysis',
];

function parseVoiceGuide(markdown: string): VoiceGuide {
  // Simple parser that extracts registers, lexicon, anti-patterns, worked examples
  const registers: VoiceGuide['registers'] = [];
  const lexicon: VoiceGuide['lexicon'] = { favor: [], avoid: [] };
  const antiPatterns: string[] = [];
  const workedExamples: VoiceGuide['workedExamples'] = [];

  // Extract registers from markdown tables/sections
  const registerMatch = markdown.match(/## (?:Voice )?Registers?\n([\s\S]*?)(?=\n## |\n---|\z)/i);
  if (registerMatch) {
    const lines = registerMatch[1].split('\n').filter(l => l.startsWith('|') && !l.includes('---'));
    for (const line of lines.slice(1)) { // skip header
      const cells = line.split('|').map(c => c.trim()).filter(Boolean);
      if (cells.length >= 4) {
        const rawName = cells[0].toLowerCase();
        const validNames = ['tactical', 'analytical', 'empathy'] as const;
        const name = validNames.includes(rawName as typeof validNames[number])
          ? (rawName as typeof validNames[number])
          : 'tactical';
        registers.push({
          name,
          sentenceLength: cells[1] || '—',
          paragraphLength: cells[2] || '—',
          tone: cells[3] || '—',
          pace: cells[4] || '—',
        });
      }
    }
  }

  // If no registers parsed, provide a default
  if (registers.length === 0) {
    registers.push({ name: 'tactical', sentenceLength: '—', paragraphLength: '—', tone: '—', pace: '—' });
  }

  return {
    identity: '',
    registers,
    styleMetrics: {},
    lexicon,
    antiPatterns,
    workedExamples,
  };
}

function parsePersonaFromMarkdown(id: string, name: string, content: string): Persona {
  const sections: { title: string; content: string }[] = [];
  const lines = content.split('\n');
  let currentTitle = '';
  let currentContent: string[] = [];
  let title = name;

  for (const line of lines) {
    if (line.startsWith('## ')) {
      if (currentTitle) {
        sections.push({ title: currentTitle, content: currentContent.join('\n').trim() });
      }
      currentTitle = line.replace('## ', '').trim();
      currentContent = [];
    } else if (line.startsWith('# ') && !title) {
      title = line.replace('# ', '').trim();
    } else {
      currentContent.push(line);
    }
  }
  if (currentTitle) {
    sections.push({ title: currentTitle, content: currentContent.join('\n').trim() });
  }

  // Extract title from first section if possible
  const titleMatch = content.match(/title[:\s]+(.+)/i);
  const personaTitle = titleMatch?.[1]?.trim() ?? sections[0]?.title ?? '';

  return {
    id,
    name: title || name,
    title: personaTitle,
    client: '',
    version: 'v1',
    sections,
  };
}

export default function BrandArtifactsPage() {
  const company = useAuthStore((s) => s.company);
  const slug = company?.slug;

  // SWR-cached hooks for primary data
  const { data: researchData, isLoading: researchLoading } = useResearchArtifacts(slug);
  const { data: kbFilesData, isLoading: kbFilesLoading } = useKBFileList(slug);

  // KB docs require dependent fetches (per-doc-type content loading)
  const [kbDocs, setKbDocs] = useState<KBDocument[]>([]);
  const [kbDocsLoading, setKbDocsLoading] = useState(true);

  // Fetch individual KB doc contents when file list is available
  useEffect(() => {
    if (!slug || !kbFilesData) return;

    const kbFiles = kbFilesData.files ?? [];

    const fetchKBDocs = async () => {
      setKbDocsLoading(true);
      const kbDocPromises = KB_DOC_TYPES.map(async (docType) => {
        const matchingFiles = kbFiles.filter((f) => f.name.startsWith(`${docType}/`));
        if (matchingFiles.length === 0) return null;

        const latestFile = matchingFiles.sort().pop();
        if (!latestFile) return null;

        try {
          const content = await apiGet<string>(
            ARTIFACTS.content('knowledge_base', slug, latestFile.name)
          );
          const markdown = typeof content === 'string' ? content : String(content);
          const wordCount = markdown.split(/\s+/).length;

          return {
            id: `${slug}-${docType}`,
            type: docType,
            client: slug,
            version: 'v1',
            markdown,
            wordCount,
            lastUpdated: new Date().toISOString(),
          } as KBDocument;
        } catch {
          return null;
        }
      });

      const kbResults = await Promise.all(kbDocPromises);
      setKbDocs(kbResults.filter((d): d is KBDocument => d !== null));
      setKbDocsLoading(false);
    };

    fetchKBDocs();
  }, [slug, kbFilesData]);

  // Parse voice guide and personas from research data
  const voiceGuide = useMemo(() => {
    if (!researchData?.style_guide?.content) return null;
    return parseVoiceGuide(researchData.style_guide.content);
  }, [researchData]);

  const voiceGuideMarkdown = researchData?.style_guide?.content ?? '';

  const personas = useMemo(() => {
    if (!researchData?.personas?.length) return [];
    return researchData.personas.map((p) =>
      parsePersonaFromMarkdown(p.id, p.name, p.content)
    );
  }, [researchData]);

  const loading = researchLoading || kbFilesLoading || (kbFilesData && kbDocsLoading);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-[40px] w-[200px]" />
        <Skeleton className="h-[40px]" />
        <Skeleton className="h-[400px]" />
      </div>
    );
  }

  return (
    <ArtifactsClient
      kbDocs={kbDocs}
      voiceGuide={voiceGuide}
      voiceGuideMarkdown={voiceGuideMarkdown}
      personas={personas}
    />
  );
}
