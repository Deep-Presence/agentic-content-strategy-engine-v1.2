'use client';

import { Button, Badge, Toast } from '@/components/ui';
import { X, Check, MessageSquare, RefreshCw, Download, Copy, Globe } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import type { ExtendedBrief } from './content-data';
import { ContentEditor } from './ContentEditor';
import { ScoringPanel } from './ScoringPanel';
import { AgentActivitySidebar } from './AgentActivitySidebar';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuthStore } from '@/stores/auth';
import { useContentStage } from '@/lib/hooks/useContent';

interface ContentViewProps {
  brief: ExtendedBrief;
  onClose: () => void;
}

export function ContentView({ brief, onClose }: ContentViewProps) {
  const slug = useAuthStore((s) => s.company?.slug);
  // M3-fix: v1.3 pipeline doesn't produce formatted.md. Show final.md for
  // approved/published briefs, enriched.md for in-progress ones.
  const editorStage = brief.stage === 'approved' ? 'final' : 'enriched';
  const { data: stageData } = useContentStage(slug ?? undefined, brief.id, editorStage);

  const [editorContent, setEditorContent] = useState('');
  const [activityCollapsed, setActivityCollapsed] = useState(true);
  const [toast, setToast] = useState<{ open: boolean; message: string; variant: 'success' | 'error' | 'info' }>({
    open: false, message: '', variant: 'info',
  });

  useEffect(() => {
    if (stageData?.content && typeof stageData.content === 'string') {
      setEditorContent(stageData.content);
    } else {
      setEditorContent(`# ${brief.title}\n\nContent is being generated. Check back soon.\n\n---\n\n**Target:** ${brief.structuralTargets.words} words\n\n**Cluster:** ${brief.targetCluster}\n\n**Query:** ${brief.targetQuery}`);
    }
  }, [stageData, brief.id, brief.title, brief.structuralTargets.words, brief.targetCluster, brief.targetQuery]);

  const showToast = useCallback((message: string, variant: 'success' | 'error' | 'info' = 'info') => {
    setToast({ open: true, message, variant });
  }, []);

  const handleApprove = () => showToast('Content approved and moved to publish queue', 'success');
  const handleFeedback = () => showToast('Feedback sent to agents', 'info');
  const handleRerun = () => showToast('Re-running all agents — coming soon', 'info');
  const handleDownload = () => showToast('Downloading markdown — coming soon', 'info');
  const handleCopy = () => {
    navigator.clipboard.writeText(editorContent).then(() => showToast('Copied to clipboard', 'success'));
  };
  const handlePublish = () => showToast('Publishing — coming soon', 'info');

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-40 bg-bg flex flex-col"
      >
        {/* Top Bar */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={onClose}
              className="p-1 rounded-sm text-text-tertiary hover:text-text-primary hover:bg-surface transition-colors cursor-pointer"
            >
              <X size={16} strokeWidth={1.5} />
            </button>
            <div className="min-w-0">
              <h2 className="text-[14px] font-semibold text-text-primary truncate">{brief.title}</h2>
              <div className="flex items-center gap-2 mt-0.5">
                <Badge variant="neutral">{brief.contentFormat}</Badge>
                <Badge variant="info">{brief.targetCluster}</Badge>
                <span className="text-[10px] text-text-tertiary">·</span>
                <Badge variant={brief.stage === 'review' ? 'warning' : brief.stage === 'approved' ? 'success' : 'info'}>
                  {brief.stage}
                </Badge>
              </div>
            </div>
          </div>
        </div>

        {/* Main: Editor + Scoring + Agent Activity */}
        <div className="flex flex-1 min-h-0">
          <div className="flex-[60] border-r border-border flex flex-col min-w-0">
            <ContentEditor
              content={editorContent}
              onChange={setEditorContent}
              onToastMessage={(msg) => showToast(msg)}
            />
          </div>
          <div className="flex-[30] min-w-[260px] max-w-[340px] bg-surface">
            <ScoringPanel brief={brief} editorContent={editorContent} />
          </div>
          <AgentActivitySidebar
            collapsed={activityCollapsed}
            onToggle={() => setActivityCollapsed(!activityCollapsed)}
          />
        </div>

        {/* Bottom Action Bar */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-border bg-surface shrink-0">
          <div className="flex items-center gap-2">
            <Button variant="primary" size="sm" onClick={handleApprove}>
              <Check size={11} strokeWidth={1.5} className="mr-1" />
              Approve
            </Button>
            <Button variant="secondary" size="sm" onClick={handleFeedback}>
              <MessageSquare size={11} strokeWidth={1.5} className="mr-1" />
              Send Back with Feedback
            </Button>
            <Button variant="ghost" size="sm" onClick={handleRerun}>
              <RefreshCw size={11} strokeWidth={1.5} className="mr-1" />
              Re-run All
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={handleDownload}>
              <Download size={11} strokeWidth={1.5} className="mr-1" />
              Download
            </Button>
            <Button variant="ghost" size="sm" onClick={handleCopy}>
              <Copy size={11} strokeWidth={1.5} className="mr-1" />
              Copy
            </Button>
            <Button variant="secondary" size="sm" onClick={handlePublish}>
              <Globe size={11} strokeWidth={1.5} className="mr-1" />
              Publish
            </Button>
          </div>
        </div>

        <Toast
          open={toast.open}
          onClose={() => setToast((t) => ({ ...t, open: false }))}
          variant={toast.variant}
          message={toast.message}
        />
      </motion.div>
    </AnimatePresence>
  );
}
