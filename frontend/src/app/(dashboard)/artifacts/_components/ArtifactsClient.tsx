'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import type { KBDocument, Persona, VoiceGuide } from '@/types';
import { HubView } from './HubView';
import { SectionDetail } from './SectionDetail';
import { PersonasListView } from './PersonasListView';
import { PersonaDetail } from './PersonaDetail';
import { VoiceGuideView } from './VoiceGuideView';
import { VisualBrandTab } from './VisualBrandTab';

interface ArtifactsClientProps {
  kbDocs: KBDocument[];
  voiceGuide: VoiceGuide | null;
  voiceGuideMarkdown: string;
  personas: Persona[];
}

const TYPE_LABELS: Record<string, string> = {
  company_overview: 'Company Overview',
  brand_perception: 'Brand Perception',
  competitor_registry: 'Competitor Registry',
  customer_reviews: 'Customer Reviews',
  weakness_analysis: 'Weakness Analysis',
};

const TYPE_TAGS: Record<string, string[]> = {
  company_overview: ['Company Profile', 'Product', 'Strategy'],
  brand_perception: ['Brand', 'Sentiment', 'Market Position'],
  competitor_registry: ['Competitors', 'Market Analysis', 'Differentiation'],
  customer_reviews: ['Customer Feedback', 'NPS', 'Feature Requests'],
  weakness_analysis: ['Gaps', 'Technical Debt', 'Remediation'],
};

type View =
  | 'hub'
  | 'kb_doc'
  | 'brand_voice'
  | 'voice_style_guide'
  | 'audience_personas'
  | 'persona_detail'
  | 'visual_brand';

export function ArtifactsClient({
  kbDocs,
  voiceGuide,
  voiceGuideMarkdown,
  personas,
}: ArtifactsClientProps) {
  const router = useRouter();
  const [currentView, setCurrentView] = useState<View>('hub');
  const [selectedDocType, setSelectedDocType] = useState<string | null>(null);
  const [selectedPersonaId, setSelectedPersonaId] = useState<string | null>(null);

  const goToHub = () => {
    setCurrentView('hub');
    setSelectedDocType(null);
    setSelectedPersonaId(null);
  };

  const handleNavigate = (id: string) => {
    // KB doc types
    if (['company_overview', 'competitor_registry', 'customer_reviews', 'weakness_analysis', 'brand_perception'].includes(id)) {
      setSelectedDocType(id);
      setCurrentView('kb_doc');
      return;
    }
    if (id === 'brand_voice') { setCurrentView('brand_voice'); return; }
    if (id === 'voice_style_guide') { setCurrentView('voice_style_guide'); return; }
    if (id === 'audience_personas') { setCurrentView('audience_personas'); return; }
    if (id === 'visual_brand') { setCurrentView('visual_brand'); return; }
  };

  // KB Doc detail
  const selectedDoc = selectedDocType ? kbDocs.find(d => d.type === selectedDocType) : null;
  const selectedPersona = selectedPersonaId ? personas.find(p => p.id === selectedPersonaId) : null;

  return (
    <div>
      {currentView === 'hub' && (
        <HubView
          kbDocs={kbDocs}
          voiceGuide={voiceGuide}
          personas={personas}
          onNavigate={handleNavigate}
          onRerun={() => router.push('/onboarding')}
        />
      )}

      {currentView === 'kb_doc' && selectedDoc && (
        <SectionDetail
          title={TYPE_LABELS[selectedDoc.type] || selectedDoc.type}
          markdown={selectedDoc.markdown}
          version={selectedDoc.version}
          lastUpdated={new Date(selectedDoc.lastUpdated).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
          createdBy="Pipeline AI"
          wordCount={selectedDoc.wordCount}
          tags={TYPE_TAGS[selectedDoc.type]}
          onBack={goToHub}
          breadcrumb={['Brand Artifact', TYPE_LABELS[selectedDoc.type] || selectedDoc.type]}
        />
      )}

      {currentView === 'brand_voice' && voiceGuide && (
        <VoiceGuideView
          voiceGuide={voiceGuide}
          markdown={voiceGuideMarkdown}
          onBack={goToHub}
        />
      )}

      {currentView === 'voice_style_guide' && voiceGuideMarkdown && (
        <SectionDetail
          title="Voice Style Guide"
          markdown={voiceGuideMarkdown}
          version="v1"
          lastUpdated="Mar 24, 2026"
          createdBy="Pipeline AI"
          wordCount={voiceGuideMarkdown.split(/\s+/).length}
          tags={['Writing Rules', 'Examples', 'Drift Check']}
          onBack={goToHub}
          breadcrumb={['Brand Artifact', 'Voice Style Guide']}
        />
      )}

      {currentView === 'audience_personas' && (
        <PersonasListView
          personas={personas}
          onBack={goToHub}
          onSelectPersona={(id) => { setSelectedPersonaId(id); setCurrentView('persona_detail'); }}
        />
      )}

      {currentView === 'persona_detail' && selectedPersona && (
        <PersonaDetail
          persona={selectedPersona}
          onBack={() => { setCurrentView('audience_personas'); setSelectedPersonaId(null); }}
        />
      )}

      {currentView === 'visual_brand' && (
        <VisualBrandTab onBack={goToHub} />
      )}
    </div>
  );
}
