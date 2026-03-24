'use client';

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { TabBar, Button } from '@/components/ui';
import { RefreshCw } from 'lucide-react';
import { useRouter } from 'next/navigation';
import type { KBDocument, Persona, VoiceGuide } from '@/types';
import { DocumentTab } from './DocumentTab';
import { VoiceGuideTab } from './VoiceGuideTab';
import { PersonasTab } from './PersonasTab';

interface ArtifactsClientProps {
  kbDocs: KBDocument[];
  voiceGuide: VoiceGuide | null;
  voiceGuideMarkdown: string;
  personas: Persona[];
}

const TABS = [
  { id: 'company_overview', label: 'Company Overview' },
  { id: 'brand_perception', label: 'Brand Perception' },
  { id: 'competitor_registry', label: 'Competitor Registry' },
  { id: 'customer_reviews', label: 'Customer Reviews' },
  { id: 'weakness_analysis', label: 'Weakness Analysis' },
  { id: 'voice_guide', label: 'Voice Style Guide' },
  { id: 'personas', label: 'Audience Personas' },
];

export function ArtifactsClient({ kbDocs, voiceGuide, voiceGuideMarkdown, personas }: ArtifactsClientProps) {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get('tab') || 'company_overview';
  const [activeTab, setActiveTab] = useState(initialTab);
  const router = useRouter();

  const activeDoc = kbDocs.find(d => d.type === activeTab);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="font-display text-[20px] font-semibold tracking-[-0.02em] text-text-primary">
          Brand Artifacts
        </h1>
      </div>

      <TabBar tabs={TABS} activeTab={activeTab} onTabClick={setActiveTab} className="mb-4" />

      {/* KB Document Tabs */}
      {activeDoc && <DocumentTab doc={activeDoc} />}

      {/* Voice Guide Tab */}
      {activeTab === 'voice_guide' && voiceGuide && (
        <VoiceGuideTab
          markdown={voiceGuideMarkdown}
          registers={voiceGuide.registers}
          lexicon={voiceGuide.lexicon}
          antiPatterns={voiceGuide.antiPatterns}
          workedExamples={voiceGuide.workedExamples}
        />
      )}

      {/* Personas Tab */}
      {activeTab === 'personas' && <PersonasTab personas={personas} />}

      {/* Re-run Pipeline Section */}
      <div className="mt-8 pt-6 border-t border-border">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[12px] text-text-secondary">Last full run: March 13, 2026</div>
          </div>
          <Button
            variant="secondary"
            onClick={() => router.push('/onboarding')}
          >
            <RefreshCw size={14} strokeWidth={1.5} className="mr-1.5" />
            Re-run Full Pipeline
          </Button>
        </div>
      </div>
    </div>
  );
}
