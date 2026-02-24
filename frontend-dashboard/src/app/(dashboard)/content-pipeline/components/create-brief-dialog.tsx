'use client';

import { useState } from 'react';
import { Dialog, DialogHeader, DialogTitle, DialogContent, DialogFooter, DialogClose } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useContentStore } from '@/stores/content-store';
import type { ContentType, ContentBriefItem } from '@/types/content';

interface CreateBriefDialogProps {
  open: boolean;
  onClose: () => void;
}

export function CreateBriefDialog({ open, onClose }: CreateBriefDialogProps) {
  const { setBriefs, briefs } = useContentStore();
  const [title, setTitle] = useState('');
  const [contentType, setContentType] = useState<ContentType>('blog');
  const [cluster, setCluster] = useState('');
  const [wordCount, setWordCount] = useState(1200);

  function handleCreate() {
    if (!title.trim()) return;

    const newBrief: ContentBriefItem = {
      id: `brief-${Date.now()}`,
      title: title.trim(),
      status: 'suggested',
      content_type: contentType,
      cluster: cluster || 'Uncategorized',
      target_word_count: wordCount,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    setBriefs([newBrief, ...briefs]);
    setTitle('');
    setCluster('');
    setWordCount(1200);
    onClose();
  }

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogClose onClose={onClose} />
      <DialogHeader>
        <DialogTitle>Create New Brief</DialogTitle>
      </DialogHeader>
      <DialogContent className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-body-sm font-sans font-medium text-cream-800">Title</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g., How do no-code builders compare to headless CMS?"
            className="w-full px-3 py-2 text-body font-body bg-white border border-[var(--border-default)] rounded-md text-cream-900 placeholder:text-cream-500 focus:border-sage-400 focus:ring-2 focus:ring-sage-400/20 outline-none"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-body-sm font-sans font-medium text-cream-800">Content Type</label>
            <select
              value={contentType}
              onChange={(e) => setContentType(e.target.value as ContentType)}
              className="w-full px-3 py-2 text-body font-sans bg-white border border-[var(--border-default)] rounded-md text-cream-800 focus:border-sage-400 focus:ring-2 focus:ring-sage-400/20 outline-none"
            >
              <option value="blog">Blog Post</option>
              <option value="guide">Guide</option>
              <option value="case_study">Case Study</option>
              <option value="product_page">Product Page</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-body-sm font-sans font-medium text-cream-800">Target Word Count</label>
            <input
              type="number"
              value={wordCount}
              onChange={(e) => setWordCount(Number(e.target.value))}
              min={300}
              max={5000}
              step={100}
              className="w-full px-3 py-2 text-body font-sans bg-white border border-[var(--border-default)] rounded-md text-cream-800 focus:border-sage-400 focus:ring-2 focus:ring-sage-400/20 outline-none tabular-nums"
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="text-body-sm font-sans font-medium text-cream-800">Cluster</label>
          <input
            type="text"
            value={cluster}
            onChange={(e) => setCluster(e.target.value)}
            placeholder="e.g., C3: Category Comparison"
            className="w-full px-3 py-2 text-body font-body bg-white border border-[var(--border-default)] rounded-md text-cream-900 placeholder:text-cream-500 focus:border-sage-400 focus:ring-2 focus:ring-sage-400/20 outline-none"
          />
        </div>
      </DialogContent>
      <DialogFooter>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button onClick={handleCreate} disabled={!title.trim()}>Create Brief</Button>
      </DialogFooter>
    </Dialog>
  );
}
