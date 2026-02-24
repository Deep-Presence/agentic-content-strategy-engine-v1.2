'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/toast';
import { useAppStore } from '@/stores/app-store';
import { useContentStore } from '@/stores/content-store';
import { artifacts } from '@/lib/api/artifacts';
import { content } from '@/lib/api/content';
import { ApiError } from '@/lib/api/client';
import { TiptapEditor } from '@/components/editor/tiptap-editor';
import { DiffToggle } from '@/components/editor/diff-toggle';
import { IntelPanel } from '@/components/editor/intel-panel';
import { ApprovalBar } from '@/components/editor/approval-bar';
import { BriefStatusBadge } from '../components/brief-status-badge';
import { ContentTypeBadge } from '../components/content-type-badge';
import { CitabilityScoreBadge } from '../components/citability-score-badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  WEBFLOW_PIPELINE_BRIEFS,
  BRIEF_003_CONTENT,
  BRIEF_003_DRAFT_CONTENT,
} from '@/lib/data/webflow-fixtures';
import type { ContentBriefItem } from '@/types/content';

// Default content for non-brief-003 briefs
const DEFAULT_CONTENT = `<h1>How Do No-Code Builders Compare to Headless CMS and Next.js?</h1>

<p>The website building landscape has evolved dramatically over the past few years. Teams now face a critical choice between three distinct approaches: visual no-code builders like Webflow, headless CMS platforms paired with frontend frameworks, and code-first solutions like Next.js.</p>

<h2>Understanding the Three Approaches</h2>

<p>Each approach serves different team compositions and technical requirements. The right choice depends on your team's technical capabilities, content velocity needs, and scalability requirements.</p>

<h3>No-Code Visual Builders</h3>

<p>No-code visual builders like Webflow allow marketing teams to design, build, and launch websites without writing code. These platforms provide drag-and-drop interfaces, visual styling tools, and built-in hosting.</p>

<p><strong>Key advantages:</strong></p>
<ul>
  <li>Zero development dependency for marketing teams</li>
  <li>Visual design-to-production workflow</li>
  <li>Built-in SEO, hosting, and performance optimization</li>
  <li>Rapid iteration on landing pages and campaigns</li>
</ul>

<h3>Headless CMS Platforms</h3>

<p>Headless CMS solutions like Contentful, Sanity, and Strapi separate content management from presentation. Content is delivered via APIs to any frontend framework.</p>

<h3>Code-First Frameworks</h3>

<p>Frameworks like Next.js provide maximum flexibility and control. Teams write React components, manage routing, and handle data fetching programmatically.</p>

<h2>Performance Comparison</h2>

<p>When evaluating Core Web Vitals scores across these three approaches, no-code builders often deliver comparable or superior performance to custom-built solutions, particularly when teams lack dedicated performance engineering resources.</p>

<h2>Decision Framework</h2>

<p>Consider these factors when choosing your approach:</p>
<ol>
  <li><strong>Team composition:</strong> Do you have dedicated developers?</li>
  <li><strong>Content velocity:</strong> How quickly do you need to publish?</li>
  <li><strong>Design complexity:</strong> How custom are your requirements?</li>
  <li><strong>Integration needs:</strong> What third-party tools must connect?</li>
</ol>

<h2>Conclusion</h2>

<p>For marketing-led organizations prioritizing speed and autonomy, no-code builders offer the best balance of capability and accessibility. For engineering-led teams building complex applications, code-first approaches provide necessary flexibility.</p>`;

const DEFAULT_DRAFT_CONTENT = `<h1>No-Code Builders vs Headless CMS vs Next.js</h1>

<p>Website building has changed. Teams must choose between no-code builders, headless CMS platforms, and code-first solutions.</p>

<h2>The Three Approaches</h2>

<p>Each approach has different tradeoffs for teams.</p>

<h3>No-Code Builders</h3>
<p>Tools like Webflow let marketing teams build without code.</p>

<h3>Headless CMS</h3>
<p>Contentful and Sanity separate content from presentation.</p>

<h3>Code-First</h3>
<p>Next.js provides maximum flexibility for developers.</p>`;

// Brief-003 specific eval scores
const BRIEF_003_EVAL_SCORES = [
  { label: 'Structural', score: 0.88, threshold: 0.8 },
  { label: 'Semantic Proximity', score: 0.72, threshold: 0.65 },
  { label: 'Style Alignment', score: 0.81, threshold: 0.7 },
  { label: 'Factual Grounding', score: 0.76, threshold: 0.7 },
];

const DEFAULT_EVAL_SCORES = [
  { label: 'Structural', score: 0.85, threshold: 0.8 },
  { label: 'Semantic Proximity', score: 0.72, threshold: 0.65 },
  { label: 'Style Alignment', score: 0.78, threshold: 0.7 },
  { label: 'Factual Grounding', score: 0.81, threshold: 0.7 },
];

const MOCK_EXEMPLARS = [
  { domain: 'agilitycms.com', similarity: 0.88, snippet: 'A headless CMS gives marketing teams the flexibility to manage content without relying on developers for every change...' },
  { domain: 'storyblok.com', similarity: 0.83, snippet: 'Marketing teams need tools that let them publish faster. Headless CMS platforms provide the API-first architecture...' },
  { domain: 'contentful.com', similarity: 0.79, snippet: 'The separation of content management from presentation allows teams to deliver consistent experiences across channels...' },
];

export default function BriefDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const { currentCompany } = useAppStore();
  const { briefs, updateBrief } = useContentStore();
  const briefId = params.briefId as string;

  const [editorContent, setEditorContent] = useState('');
  const [previousContent, setPreviousContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [approvalLoading, setApprovalLoading] = useState(false);

  const brief = briefs.find((b) => b.id === briefId)
    ?? WEBFLOW_PIPELINE_BRIEFS.find((b) => b.id === briefId);

  const isBrief003 = briefId === 'brief-003';
  const mockContent = isBrief003 ? BRIEF_003_CONTENT : DEFAULT_CONTENT;
  const mockDraft = isBrief003 ? BRIEF_003_DRAFT_CONTENT : DEFAULT_DRAFT_CONTENT;
  const activeEvalScores = isBrief003 ? BRIEF_003_EVAL_SCORES : DEFAULT_EVAL_SCORES;

  const loadContent = useCallback(async () => {
    setLoading(true);
    const slug = currentCompany || 'webflow';

    try {
      const finalContent = await artifacts.getContent<string>('content', slug, `content/${briefId}/final.md`);
      setEditorContent(finalContent);
    } catch {
      setEditorContent(mockContent);
    }

    try {
      const draftContent = await artifacts.getContent<string>('content', slug, `content/${briefId}/draft.md`);
      setPreviousContent(draftContent);
    } catch {
      setPreviousContent(mockDraft);
    }

    setLoading(false);
  }, [currentCompany, briefId, mockContent, mockDraft]);

  useEffect(() => {
    loadContent();
  }, [loadContent]);

  async function handleApprove() {
    setApprovalLoading(true);
    try {
      await content.approve(briefId, { brief_id: briefId, decision: 'approve' });
      updateBrief(briefId, { status: 'published' });
      toast('Content approved and published', 'success');
      router.push('/content-pipeline');
    } catch (err) {
      if (err instanceof ApiError) {
        toast(err.message, 'error');
      } else {
        toast('Failed to approve content', 'error');
      }
    } finally {
      setApprovalLoading(false);
    }
  }

  async function handleEdit(notes: string) {
    setApprovalLoading(true);
    try {
      await content.approve(briefId, { brief_id: briefId, decision: 'edit', editor_notes: notes });
      updateBrief(briefId, { status: 'drafting' });
      toast('Sent back for revision', 'success');
      router.push('/content-pipeline');
    } catch (err) {
      if (err instanceof ApiError) {
        toast(err.message, 'error');
      } else {
        toast('Failed to send edit request', 'error');
      }
    } finally {
      setApprovalLoading(false);
    }
  }

  async function handleReject() {
    setApprovalLoading(true);
    try {
      await content.approve(briefId, { brief_id: briefId, decision: 'reject' });
      updateBrief(briefId, { status: 'draft_saved' });
      toast('Content rejected and saved as draft', 'info');
      router.push('/content-pipeline');
    } catch (err) {
      if (err instanceof ApiError) {
        toast(err.message, 'error');
      } else {
        toast('Failed to reject content', 'error');
      }
    } finally {
      setApprovalLoading(false);
    }
  }

  const isReview = brief?.status === 'review';
  const isPublished = brief?.status === 'published';
  const isEditable = isReview;

  // Word count from editor content
  const currentWordCount = editorContent
    ? editorContent.replace(/<[^>]*>/g, ' ').split(/\s+/).filter(Boolean).length
    : 0;

  const currentHeaderCount = editorContent
    ? (editorContent.match(/<h[1-6]/g) || []).length
    : 0;

  return (
    <div className="flex flex-col h-full -m-6">
      {/* Top navigation bar */}
      <div className="px-6 py-3 border-b border-[var(--border-default)] bg-white">
        <div className="flex items-center gap-3 mb-2">
          <Link
            href="/content-pipeline"
            className="flex items-center gap-1 text-body-sm font-sans text-cream-600 hover:text-cream-900 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Pipeline
          </Link>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-serif text-heading-2 text-cream-950">
              {brief?.title ?? 'Loading...'}
            </h1>
            <div className="flex items-center gap-2 mt-1">
              {brief && (
                <>
                  <BriefStatusBadge status={brief.status} />
                  <span className="text-cream-400">|</span>
                  <span className="text-body-sm font-sans text-cream-600">{brief.cluster}</span>
                  <span className="text-cream-400">|</span>
                  <ContentTypeBadge type={brief.content_type} />
                  {brief.citability_score != null && (
                    <>
                      <span className="text-cream-400">|</span>
                      <span className="text-body-sm font-sans text-cream-600">Citability:</span>
                      <CitabilityScoreBadge score={brief.citability_score} size="sm" />
                    </>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Editor (left, ~60%) */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {loading ? (
            <div className="space-y-3">
              <Skeleton className="h-8 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-6 w-1/2 mt-4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
            </div>
          ) : (
            <>
              <div className="flex items-center justify-end">
                <DiffToggle
                  previousContent={previousContent.replace(/<[^>]*>/g, '')}
                  currentContent={editorContent.replace(/<[^>]*>/g, '')}
                />
              </div>

              <TiptapEditor
                content={editorContent}
                editable={isEditable}
                onChange={setEditorContent}
              />
            </>
          )}
        </div>

        {/* Intel Panel (right, ~40%) */}
        <div className="w-[380px] shrink-0 border-l border-[var(--border-default)] bg-[var(--bg-secondary)] overflow-y-auto p-4">
          <IntelPanel
            targetSignals={isBrief003 ? {
              word_count_range: [977, 4268],
              reading_level_range: [13.0, 14.3],
              header_count_range: [35, 40],
              h2_count: 3,
              h3_count: 34,
              content_patterns: ['FAQ', 'Key Takeaways', 'Step-by-Step', 'Tables'],
            } : {
              word_count_range: [brief?.target_word_count ? brief.target_word_count - 50 : 1040, brief?.target_word_count ? brief.target_word_count + 50 : 1140],
              reading_level_range: [12.0, 14.6],
              header_count_range: [12, 15],
              h2_count: 3,
              h3_count: 9,
              content_patterns: ['Step-by-Step', 'Comparison Matrix', 'Decision Framework'],
            }}
            currentMetrics={{
              word_count: currentWordCount,
              header_count: currentHeaderCount,
              reading_level: isBrief003 ? 13.6 : 13.2,
            }}
            gapScore={isBrief003 ? 0.2535 : 0.244}
            gapClassification="Significant Gap"
            evalScores={activeEvalScores}
            revisionHistory={[
              { cycle: 1, scores: activeEvalScores.map((s) => ({ ...s, score: s.score - 0.15 })), passed: false },
              { cycle: 2, scores: activeEvalScores, passed: true },
            ]}
            exemplars={MOCK_EXEMPLARS}
            briefId={briefId}
            onRegenerate={() => toast('Regeneration triggered', 'info')}
          />
        </div>
      </div>

      {/* Approval bar (only for review status) */}
      {isReview && (
        <ApprovalBar
          onApprove={handleApprove}
          onEdit={handleEdit}
          onReject={handleReject}
          loading={approvalLoading}
        />
      )}
    </div>
  );
}
