'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogContent,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import type { KnowledgeDoc } from '@/types/brand';

interface KnowledgeDocEditorProps {
  open: boolean;
  onClose: () => void;
  doc?: KnowledgeDoc;
  onSave: (doc: KnowledgeDoc) => void;
  projectId?: string;
}

export function KnowledgeDocEditor({
  open,
  onClose,
  doc,
  onSave,
  projectId,
}: KnowledgeDocEditorProps) {
  const [title, setTitle] = useState(doc?.title ?? '');
  const [type, setType] = useState<KnowledgeDoc['type']>(doc?.type ?? 'other');
  const [content, setContent] = useState(doc?.content ?? '');
  const { toast } = useToast();

  const isEditing = !!doc;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;

    onSave({
      id: doc?.id ?? crypto.randomUUID(),
      title: title.trim(),
      type,
      content: content.trim(),
      project_id: projectId ?? doc?.project_id,
    });

    toast(
      isEditing ? 'Document updated' : 'Document added',
      'success'
    );

    if (!isEditing) {
      setTitle('');
      setType('other');
      setContent('');
    }
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} className="max-w-2xl">
      <DialogClose onClose={onClose} />
      <DialogHeader>
        <DialogTitle>
          {isEditing ? 'Edit Document' : 'Add Knowledge Document'}
        </DialogTitle>
      </DialogHeader>
      <form onSubmit={handleSubmit}>
        <DialogContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Document Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Brand Guidelines"
              required
            />
            <Select
              label="Type"
              value={type}
              onChange={(e) => setType(e.target.value as KnowledgeDoc['type'])}
            >
              <option value="brand_guidelines">Brand Guidelines</option>
              <option value="product_context">Product Context</option>
              <option value="voice_recording">Voice & Tone</option>
              <option value="style_guide">Style Guide</option>
              <option value="other">Other</option>
            </Select>
          </div>
          <div>
            <label className="block text-body-sm font-sans font-medium text-cream-800 mb-1.5">
              Content (Markdown supported)
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Paste or type your knowledge document content here..."
              rows={14}
              required
              className="w-full px-3 py-2 bg-white border border-[var(--border-default)] rounded-md font-body text-body text-cream-900 placeholder:text-cream-600 focus:outline-none focus:ring-2 focus:ring-terracotta-400/20 focus:border-terracotta-400 resize-y"
            />
          </div>
        </DialogContent>
        <DialogFooter>
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={!title.trim() || !content.trim()}>
            {isEditing ? 'Save Changes' : 'Add Document'}
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
