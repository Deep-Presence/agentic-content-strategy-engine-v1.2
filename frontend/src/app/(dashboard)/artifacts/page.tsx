import { Suspense } from 'react';
import { getKnowledgeBase } from '@/data/knowledge-base';
import { getVoiceGuide, getVoiceGuideMarkdown } from '@/data/voice-guide';
import { getPersonas } from '@/data/personas';
import { ArtifactsClient } from './_components/ArtifactsClient';

export default function BrandArtifactsPage() {
  const kbDocs = getKnowledgeBase();
  const voiceGuide = getVoiceGuide();
  const voiceGuideMarkdown = getVoiceGuideMarkdown();
  const personas = getPersonas();

  return (
    <Suspense>
      <ArtifactsClient
        kbDocs={kbDocs}
        voiceGuide={voiceGuide}
        voiceGuideMarkdown={voiceGuideMarkdown}
        personas={personas}
      />
    </Suspense>
  );
}
