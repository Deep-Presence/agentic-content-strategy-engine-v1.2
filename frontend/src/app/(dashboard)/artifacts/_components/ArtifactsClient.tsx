'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import type { KBDocument, VoiceGuide } from '@/types';
import type { PersonaListItemAPI, VersionEntry } from '../_lib/types';
import { useArtifactsData } from '../_hooks/useArtifactsData';
import { usePersonaContent } from '../_hooks/usePersonaContent';
import { extractVersions, extractGuideVersions, extractPersonaVersions } from '../_lib/versions';
import { parseVoiceGuideMarkdown } from '../_lib/parse-voice-guide';
import { buildKBDocument } from '../_lib/adapters';
import { HubView } from './HubView';
import { SectionDetail } from './SectionDetail';
import { PersonasListView } from './PersonasListView';
import { PersonaDetail } from './PersonaDetail';
import { VoiceGuideView } from './VoiceGuideView';
import { VisualBrandTab } from './VisualBrandTab';
import { HubSkeleton, DetailSkeleton } from './ArtifactsSkeleton';
import { UploadModal } from './UploadModal';
import { Card, Button } from '@/components/ui';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import type { KBDocType } from '../_lib/types';

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

// ── Persona detail loader (lazy content fetch + version switching) ───

function PersonaDetailLoader({
  persona,
  versions,
  onBack,
  onUpload,
}: {
  persona: PersonaListItemAPI;
  versions: VersionEntry[];
  onBack: () => void;
  onUpload?: () => void;
}) {
  const { companySlug } = useAuth();
  const [activeVersion, setActiveVersion] = useState(persona.current_version);
  const [activeFilePath, setActiveFilePath] = useState<string | undefined>(undefined);
  const { persona: fullPersona, isLoading, error } = usePersonaContent(
    companySlug,
    persona.persona_id,
    activeVersion,
  );

  const handleVersionSelect = (entry: VersionEntry) => {
    setActiveFilePath(entry.filePath);
    if (entry.version > 0) {
      setActiveVersion(entry.version);
    }
  };

  if (isLoading) return <DetailSkeleton />;

  if (error || !fullPersona) {
    return (
      <Card className="!p-8 text-center">
        <AlertTriangle size={24} className="text-warning mx-auto mb-3" />
        <p className="text-[14px] text-text-secondary mb-3">{error || 'Unable to load persona.'}</p>
        <Button variant="secondary" onClick={onBack}>Go Back</Button>
      </Card>
    );
  }

  return (
    <PersonaDetail
      persona={fullPersona}
      onBack={onBack}
      versions={versions}
      activeFilePath={activeFilePath}
      onSelectVersion={handleVersionSelect}
      onUpload={onUpload}
    />
  );
}

// ── Main client component ───────────────────────────────

export function ArtifactsClient() {
  const router = useRouter();
  const { companySlug } = useAuth();
  const {
    kbDocs, voiceGuide, voiceGuideRaw, personas, kbHealth,
    kbFileList, vsgFileList, personaFileList,
    isLoading, error, refetch,
  } = useArtifactsData();

  const [currentView, setCurrentView] = useState<View>('hub');
  const [selectedDocType, setSelectedDocType] = useState<string | null>(null);
  const [selectedPersonaId, setSelectedPersonaId] = useState<string | null>(null);

  // Overridden content when user picks a non-current version
  const [overrideKbDoc, setOverrideKbDoc] = useState<KBDocument | null>(null);
  const [overrideVoiceGuide, setOverrideVoiceGuide] = useState<VoiceGuide | null>(null);
  const [overrideVoiceGuideRaw, setOverrideVoiceGuideRaw] = useState<string | null>(null);
  const [versionLoading, setVersionLoading] = useState(false);

  // Track the user's actively selected filePath per artifact type
  const [activeKBFilePath, setActiveKBFilePath] = useState<string | undefined>(undefined);
  const [activeVSGFilePath, setActiveVSGFilePath] = useState<string | undefined>(undefined);

  // Upload modal state
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadArtifactType, setUploadArtifactType] = useState('');
  const [uploadSubPath, setUploadSubPath] = useState<string | undefined>(undefined);

  const handleOpenUpload = useCallback((artifactType: string, subPath?: string) => {
    setUploadArtifactType(artifactType);
    setUploadSubPath(subPath);
    setUploadModalOpen(true);
  }, []);

  const goToHub = () => {
    setCurrentView('hub');
    setSelectedDocType(null);
    setSelectedPersonaId(null);
    setOverrideKbDoc(null);
    setOverrideVoiceGuide(null);
    setOverrideVoiceGuideRaw(null);
    setActiveKBFilePath(undefined);
    setActiveVSGFilePath(undefined);
  };

  const handleNavigate = (id: string) => {
    // Clear overrides when navigating to a new artifact
    setOverrideKbDoc(null);
    setOverrideVoiceGuide(null);
    setOverrideVoiceGuideRaw(null);

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

  // ── Version switching handlers ────────────────────────

  const handleKBVersionSelect = useCallback(async (entry: VersionEntry) => {
    if (!companySlug || !selectedDocType) return;
    setActiveKBFilePath(entry.filePath);
    setVersionLoading(true);
    try {
      const { api } = await import('@/lib/api-client');
      const content = await api.getText(`/api/v1/artifacts/knowledge_base/${companySlug}/${entry.filePath}`);
      const doc = buildKBDocument(selectedDocType as KBDocType, content, kbHealth);
      setOverrideKbDoc({ ...doc, version: entry.label });
    } catch {
      // Stay on current version if fetch fails
    } finally {
      setVersionLoading(false);
    }
  }, [companySlug, selectedDocType, kbHealth]);

  const handleVSGVersionSelect = useCallback(async (entry: VersionEntry) => {
    if (!companySlug) return;
    setActiveVSGFilePath(entry.filePath);
    setVersionLoading(true);
    try {
      const { api } = await import('@/lib/api-client');
      const content = await api.getText(`/api/v1/artifacts/voice_style_guide/${companySlug}/${entry.filePath}`);
      setOverrideVoiceGuideRaw(content);
      setOverrideVoiceGuide(parseVoiceGuideMarkdown(content));
    } catch {
      // Stay on current version
    } finally {
      setVersionLoading(false);
    }
  }, [companySlug]);

  // ── Loading / Error states ────────────────────────────

  if (isLoading && currentView === 'hub') {
    return <HubSkeleton />;
  }

  if (error && kbDocs.length === 0 && !voiceGuide && personas.length === 0) {
    return (
      <Card className="!p-10 text-center">
        <AlertTriangle size={28} className="text-warning mx-auto mb-4" />
        <h2 className="text-[16px] font-semibold text-text-primary mb-2">Unable to load artifacts</h2>
        <p className="text-[13px] text-text-secondary mb-4 max-w-[400px] mx-auto">{error}</p>
        <Button variant="primary" onClick={refetch}>
          <RefreshCw size={13} strokeWidth={1.5} className="mr-1.5" />
          Try Again
        </Button>
      </Card>
    );
  }

  // ── Derived data ──────────────────────────────────────

  const selectedDoc = selectedDocType
    ? (overrideKbDoc?.type === selectedDocType ? overrideKbDoc : kbDocs.find(d => d.type === selectedDocType))
    : null;
  const selectedPersona = selectedPersonaId ? personas.find(p => p.persona_id === selectedPersonaId) : null;

  // Compute version lists from file listings
  const kbVersions = selectedDocType && kbFileList
    ? extractVersions(kbFileList, `${selectedDocType}/`, kbHealth?.doc_health?.[selectedDocType]?.current_version ?? 1)
    : [];

  const vsgVersions = vsgFileList
    ? extractGuideVersions(vsgFileList, 1) // current version from VSG response
    : [];

  const personaVersions = selectedPersona && personaFileList
    ? extractPersonaVersions(personaFileList, selectedPersona.persona_id, selectedPersona.current_version)
    : [];

  const activeVoiceGuide = overrideVoiceGuide ?? voiceGuide;
  const activeVoiceGuideRaw = overrideVoiceGuideRaw ?? voiceGuideRaw;

  return (
    <div>
      {currentView === 'hub' && (
        <HubView
          kbDocs={kbDocs}
          voiceGuide={voiceGuide}
          personas={personas}
          kbHealth={kbHealth}
          onNavigate={handleNavigate}
          onRerun={() => router.push('/onboarding')}
        />
      )}

      {currentView === 'kb_doc' && selectedDoc && (
        <SectionDetail
          title={TYPE_LABELS[selectedDoc.type] || selectedDoc.type}
          markdown={versionLoading ? 'Loading...' : selectedDoc.markdown}
          version={selectedDoc.version}
          lastUpdated={new Date(selectedDoc.lastUpdated).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
          createdBy="Pipeline AI"
          wordCount={selectedDoc.wordCount}
          tags={TYPE_TAGS[selectedDoc.type]}
          onBack={goToHub}
          breadcrumb={['Brand Artifact', TYPE_LABELS[selectedDoc.type] || selectedDoc.type]}
          versions={kbVersions}
          activeFilePath={activeKBFilePath}
          onSelectVersion={handleKBVersionSelect}
          onUpload={() => handleOpenUpload('knowledge_base', selectedDocType ?? undefined)}
        />
      )}

      {currentView === 'brand_voice' && activeVoiceGuide && (
        <VoiceGuideView
          voiceGuide={activeVoiceGuide}
          markdown={activeVoiceGuideRaw}
          onBack={goToHub}
          versions={vsgVersions}
          activeFilePath={activeVSGFilePath}
          onSelectVersion={handleVSGVersionSelect}
          onUpload={() => handleOpenUpload('voice_style_guide', 'guide')}
        />
      )}

      {currentView === 'voice_style_guide' && activeVoiceGuideRaw && (
        <SectionDetail
          title="Voice Style Guide"
          markdown={versionLoading ? 'Loading...' : activeVoiceGuideRaw}
          version="v1"
          lastUpdated="—"
          createdBy="Pipeline AI"
          wordCount={activeVoiceGuideRaw.split(/\s+/).length}
          tags={['Writing Rules', 'Examples', 'Drift Check']}
          onBack={goToHub}
          breadcrumb={['Brand Artifact', 'Voice Style Guide']}
          versions={vsgVersions}
          activeFilePath={activeVSGFilePath}
          onSelectVersion={handleVSGVersionSelect}
          onUpload={() => handleOpenUpload('voice_style_guide', 'guide')}
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
        <PersonaDetailLoader
          persona={selectedPersona}
          versions={personaVersions}
          onBack={() => { setCurrentView('audience_personas'); setSelectedPersonaId(null); }}
          onUpload={() => handleOpenUpload('audience_personas', selectedPersona?.persona_id)}
        />
      )}

      {currentView === 'visual_brand' && (
        <VisualBrandTab onBack={goToHub} />
      )}

      {/* Upload Modal */}
      <UploadModal
        open={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        artifactType={uploadArtifactType}
        slug={companySlug}
        subPath={uploadSubPath}
        onUploadComplete={refetch}
      />
    </div>
  );
}
