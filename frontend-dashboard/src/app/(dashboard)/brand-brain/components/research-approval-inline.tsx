'use client';

import { useState } from 'react';
import { CheckCircle, Pencil, XCircle, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { research } from '@/lib/api/research';
import { cn } from '@/lib/utils/cn';

interface ResearchApprovalInlineProps {
  runId: string;
  stage: string;
  draftContent: string;
  onApproved?: () => void;
  onRevised?: () => void;
  onRejected?: () => void;
}

const STAGE_LABELS: Record<string, string> = {
  company: 'Company Context',
  persona: 'Persona',
  style: 'Style Guide',
};

export function ResearchApprovalInline({
  runId,
  stage,
  draftContent,
  onApproved,
  onRevised,
  onRejected,
}: ResearchApprovalInlineProps) {
  const [showRevisionNote, setShowRevisionNote] = useState(false);
  const [revisionNote, setRevisionNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { toast } = useToast();

  const handleApprove = async () => {
    setSubmitting(true);
    try {
      await research.approve(runId, { decision: 'approve' });
      toast(`${STAGE_LABELS[stage] ?? stage} approved`, 'success');
      onApproved?.();
    } catch {
      toast('Failed to approve', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRevise = async () => {
    if (!revisionNote.trim()) {
      toast('Please add a revision note', 'warning');
      return;
    }
    setSubmitting(true);
    try {
      await research.approve(runId, {
        decision: 'revise',
        revision_note: revisionNote.trim(),
      });
      toast('Revision requested — agent will revise the draft', 'info');
      setShowRevisionNote(false);
      setRevisionNote('');
      onRevised?.();
    } catch {
      toast('Failed to request revision', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    setSubmitting(true);
    try {
      await research.approve(runId, { decision: 'reject' });
      toast(`${STAGE_LABELS[stage] ?? stage} rejected`, 'info');
      onRejected?.();
    } catch {
      toast('Failed to reject', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-md border border-terracotta-200 shadow-[var(--shadow-sm)]">
      <div className="flex items-center gap-2 p-4 border-b border-[var(--border-subtle)] bg-terracotta-50/50 rounded-t-md">
        <FileText className="h-4 w-4 text-terracotta-400" />
        <h4 className="font-sans text-heading-4 font-semibold text-cream-950">
          {STAGE_LABELS[stage] ?? stage} Draft Ready for Review
        </h4>
      </div>

      <div className="p-4">
        <div className="max-h-[400px] overflow-y-auto border border-[var(--border-subtle)] rounded-md p-4 bg-cream-100/50">
          <div className="prose-brand max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeSanitize]}
              components={{
                h1: ({ children }) => (
                  <h1 className="font-serif text-heading-2 font-semibold text-cream-950 mt-4 mb-2 first:mt-0">
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className="font-serif text-heading-3 font-semibold text-cream-950 mt-3 mb-2">
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 className="font-serif text-heading-4 font-semibold text-cream-900 mt-3 mb-1">
                    {children}
                  </h3>
                ),
                p: ({ children }) => (
                  <p className="font-body text-body-sm text-cream-800 mb-2 leading-relaxed">
                    {children}
                  </p>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc list-inside font-body text-body-sm text-cream-800 mb-2 space-y-1 ml-2">
                    {children}
                  </ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal list-inside font-body text-body-sm text-cream-800 mb-2 space-y-1 ml-2">
                    {children}
                  </ol>
                ),
                strong: ({ children }) => (
                  <strong className="font-semibold text-cream-950">{children}</strong>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="border-l-3 border-terracotta-400 pl-3 py-1 my-2 text-cream-700 italic text-body-sm">
                    {children}
                  </blockquote>
                ),
              }}
            >
              {draftContent}
            </ReactMarkdown>
          </div>
        </div>
      </div>

      <div className="p-4 pt-0 space-y-3">
        {showRevisionNote && (
          <div className="space-y-2">
            <label className="block text-body-sm font-sans font-medium text-cream-800">
              Revision Note
            </label>
            <textarea
              value={revisionNote}
              onChange={(e) => setRevisionNote(e.target.value)}
              placeholder="Describe what should be changed..."
              rows={3}
              className="w-full px-3 py-2 bg-white border border-[var(--border-default)] rounded-md font-body text-body-sm text-cream-900 placeholder:text-cream-600 focus:outline-none focus:ring-2 focus:ring-terracotta-400/20 focus:border-terracotta-400 resize-none"
            />
          </div>
        )}

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={handleApprove}
            disabled={submitting}
          >
            <CheckCircle className="h-3.5 w-3.5 mr-1.5" />
            Approve
          </Button>
          {showRevisionNote ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={handleRevise}
              disabled={submitting || !revisionNote.trim()}
            >
              <Pencil className="h-3.5 w-3.5 mr-1.5" />
              Submit Revision
            </Button>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowRevisionNote(true)}
              disabled={submitting}
            >
              <Pencil className="h-3.5 w-3.5 mr-1.5" />
              Revise
            </Button>
          )}
          <Button
            variant="danger"
            size="sm"
            onClick={handleReject}
            disabled={submitting}
          >
            <XCircle className="h-3.5 w-3.5 mr-1.5" />
            Reject
          </Button>
        </div>
      </div>
    </div>
  );
}
