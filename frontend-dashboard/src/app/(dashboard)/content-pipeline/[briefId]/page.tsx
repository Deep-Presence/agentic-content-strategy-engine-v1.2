'use client';

import { useEffect, useState, useCallback, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft, PanelRightClose, PanelRightOpen,
  ListTree, Eye, Pencil,
} from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
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
import { cn } from '@/lib/utils/cn';
import {
  WEBFLOW_PIPELINE_BRIEFS,
  BRIEF_003_CONTENT,
  BRIEF_003_DRAFT_CONTENT,
} from '@/lib/data/webflow-fixtures';
import type { ContentBriefItem } from '@/types/content';

// ── Mock content ────────────────────────────────────────────

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

<p>Headless CMS solutions like Contentful, Sanity, and Strapi separate content management from presentation. Content is delivered via APIs to any frontend framework, providing maximum flexibility in how content is consumed and displayed.</p>

<h3>Code-First Frameworks</h3>

<p>Frameworks like Next.js provide maximum flexibility and control. Teams write React components, manage routing, and handle data fetching programmatically. This approach requires dedicated engineering resources but offers unmatched customization.</p>

<h2>Performance Comparison</h2>

<p>When evaluating Core Web Vitals scores across these three approaches, no-code builders often deliver comparable or superior performance to custom-built solutions, particularly when teams lack dedicated performance engineering resources.</p>

<p>In benchmark tests across 500 enterprise sites, the results were revealing:</p>

<ol>
  <li><strong>Webflow sites:</strong> Average LCP of 1.8s, CLS of 0.05</li>
  <li><strong>Headless + Next.js:</strong> Average LCP of 2.1s, CLS of 0.08</li>
  <li><strong>WordPress:</strong> Average LCP of 3.2s, CLS of 0.15</li>
</ol>

<h2>Decision Framework</h2>

<p>Consider these factors when choosing your approach:</p>
<ol>
  <li><strong>Team composition:</strong> Do you have dedicated developers?</li>
  <li><strong>Content velocity:</strong> How quickly do you need to publish?</li>
  <li><strong>Design complexity:</strong> How custom are your requirements?</li>
  <li><strong>Integration needs:</strong> What third-party tools must connect?</li>
</ol>

<blockquote><p>"The best website builder is the one that matches your team's skill set. No-code tools have closed the gap with custom development for 80% of marketing use cases." — Forrester Research, 2024</p></blockquote>

<h2>Conclusion</h2>

<p>For marketing-led organizations prioritizing speed and autonomy, no-code builders offer the best balance of capability and accessibility. For engineering-led teams building complex applications, code-first approaches provide necessary flexibility. The growing middle ground — headless CMS with composable frontends — serves teams that need both content agility and engineering control.</p>`;

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

// ── Document outline helper ─────────────────────────────────

interface DocHeading {
  level: number;
  text: string;
}

function extractHeadings(html: string): DocHeading[] {
  const regex = /<h([1-4])[^>]*>(.*?)<\/h[1-4]>/gi;
  const headings: DocHeading[] = [];
  let match: RegExpExecArray | null;
  while ((match = regex.exec(html)) !== null) {
    headings.push({
      level: parseInt(match[1]),
      text: match[2].replace(/<[^>]*>/g, ''),
    });
  }
  return headings;
}

// ── Page ────────────────────────────────────────────────────

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
  const [showIntel, setShowIntel] = useState(true);
  const [showOutline, setShowOutline] = useState(true);

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

  // ── Handlers ──

  async function handleApprove() {
    setApprovalLoading(true);
    try {
      await content.approve(briefId, { brief_id: briefId, decision: 'approve' });
      updateBrief(briefId, { status: 'published' });
      toast('Content approved and published', 'success');
      router.push('/content-pipeline');
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Failed to approve content', 'error');
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
      toast(err instanceof ApiError ? err.message : 'Failed to send edit request', 'error');
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
      toast(err instanceof ApiError ? err.message : 'Failed to reject content', 'error');
    } finally {
      setApprovalLoading(false);
    }
  }

  // ── Derived state ──

  const isReview = brief?.status === 'review';
  const isEditable = isReview;
  const headings = useMemo(() => extractHeadings(editorContent), [editorContent]);

  const currentWordCount = editorContent
    ? editorContent.replace(/<[^>]*>/g, ' ').split(/\s+/).filter(Boolean).length
    : 0;

  const currentHeaderCount = editorContent
    ? (editorContent.match(/<h[1-6]/g) || []).length
    : 0;

  const targetWc = isBrief003
    ? { min: 977, max: 4268 }
    : brief?.target_word_count
      ? { min: brief.target_word_count - 50, max: brief.target_word_count + 50 }
      : { min: 1040, max: 1140 };

  // ── Render ──

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] -m-6">
      {/* ━━ Top bar ━━ */}
      <div className="shrink-0 px-6 py-3 border-b border-[var(--border-default)] bg-white">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 mb-1.5 text-body-sm font-sans">
          <Link
            href="/content-pipeline"
            className="flex items-center gap-1 text-cream-600 hover:text-cream-900 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Pipeline
          </Link>
          <span className="text-cream-300">/</span>
          <span className="text-cream-500 truncate max-w-[300px]">
            {brief?.title ?? briefId}
          </span>
        </div>

        {/* Title row */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <h1 className="font-serif text-heading-3 text-cream-950 truncate">
              {brief?.title ?? 'Loading...'}
            </h1>
            {brief && (
              <div className="flex items-center gap-2 shrink-0">
                <BriefStatusBadge status={brief.status} />
                <ContentTypeBadge type={brief.content_type} />
                {brief.citability_score != null && (
                  <CitabilityScoreBadge score={brief.citability_score} size="sm" />
                )}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Edit mode indicator */}
            {isEditable ? (
              <span className="flex items-center gap-1.5 text-caption font-sans text-sage-400">
                <Pencil className="h-3 w-3" />
                Editing
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-caption font-sans text-cream-500">
                <Eye className="h-3 w-3" />
                Read-only
              </span>
            )}

            <span className="w-px h-4 bg-cream-300" />

            {/* Outline toggle */}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowOutline(!showOutline)}
              title={showOutline ? 'Hide outline' : 'Show outline'}
              className={cn(showOutline && 'bg-cream-200')}
            >
              <ListTree className="h-4 w-4" />
            </Button>

            {/* Intel panel toggle */}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowIntel(!showIntel)}
              title={showIntel ? 'Hide intel panel' : 'Show intel panel'}
              className={cn(showIntel && 'bg-cream-200')}
            >
              {showIntel ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </div>

      {/* ━━ Main content area ━━ */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── Document outline ── */}
        {showOutline && headings.length > 0 && (
          <div className="w-[210px] shrink-0 border-r border-[var(--border-default)] bg-cream-50 overflow-y-auto py-3 px-2">
            <h3 className="text-[10px] font-sans font-semibold text-cream-500 uppercase tracking-widest mb-2 px-2">
              Outline
            </h3>
            <nav className="space-y-0.5">
              {headings.map((h, i) => (
                <div
                  key={i}
                  className={cn(
                    'px-2 py-1 rounded text-caption font-sans truncate transition-colors',
                    h.level === 1 && 'font-medium text-cream-900',
                    h.level === 2 && 'pl-4 text-cream-700',
                    h.level === 3 && 'pl-6 text-cream-600',
                    h.level === 4 && 'pl-8 text-cream-500 text-[10px]',
                  )}
                  title={h.text}
                >
                  {h.text}
                </div>
              ))}
            </nav>

            {/* Quick stats */}
            <div className="mt-4 pt-3 border-t border-cream-200 space-y-1.5 px-2">
              <div className="flex justify-between text-[10px] font-sans text-cream-500">
                <span>Words</span>
                <span className="tabular-nums font-medium text-cream-700">{currentWordCount.toLocaleString()}</span>
              </div>
              <div className="flex justify-between text-[10px] font-sans text-cream-500">
                <span>Headings</span>
                <span className="tabular-nums font-medium text-cream-700">{currentHeaderCount}</span>
              </div>
              {brief?.cluster && (
                <div className="flex justify-between text-[10px] font-sans text-cream-500">
                  <span>Cluster</span>
                  <span className="text-cream-700 truncate ml-2">{brief.cluster}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Editor panel ── */}
        <div className="flex-1 overflow-y-auto bg-[var(--bg-secondary)]">
          {loading ? (
            <div className="max-w-[820px] mx-auto p-8 space-y-4">
              <Skeleton className="h-8 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-7 w-1/2 mt-6" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-4/5" />
              <Skeleton className="h-7 w-2/5 mt-6" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
            </div>
          ) : (
            <div className="max-w-[820px] mx-auto p-6 space-y-4">
              {/* Diff toggle */}
              <div className="flex items-center justify-end">
                <DiffToggle
                  previousContent={previousContent.replace(/<[^>]*>/g, '')}
                  currentContent={editorContent.replace(/<[^>]*>/g, '')}
                />
              </div>

              {/* Editor */}
              <TiptapEditor
                content={editorContent}
                editable={isEditable}
                onChange={setEditorContent}
                targetWordCount={targetWc}
              />
            </div>
          )}
        </div>

        {/* ── Intel panel ── */}
        {showIntel && (
          <div className="w-[360px] shrink-0 border-l border-[var(--border-default)] bg-white overflow-y-auto">
            <div className="p-4">
              <IntelPanel
                targetSignals={isBrief003 ? {
                  word_count_range: [977, 4268],
                  reading_level_range: [13.0, 14.3],
                  header_count_range: [35, 40],
                  h2_count: 3,
                  h3_count: 34,
                  content_patterns: ['FAQ', 'Key Takeaways', 'Step-by-Step', 'Tables'],
                } : {
                  word_count_range: [targetWc.min, targetWc.max],
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
        )}
      </div>

      {/* ━━ Approval bar ━━ */}
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
