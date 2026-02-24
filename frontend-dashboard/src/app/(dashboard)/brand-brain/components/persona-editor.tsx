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
import type { Persona } from '@/types/brand';

interface PersonaEditorProps {
  open: boolean;
  onClose: () => void;
  persona?: Persona;
  onSave: (persona: Persona) => void;
}

export function PersonaEditor({ open, onClose, persona, onSave }: PersonaEditorProps) {
  const [name, setName] = useState(persona?.name ?? '');
  const [type, setType] = useState<'icp' | 'secondary'>(persona?.type ?? 'secondary');
  const [content, setContent] = useState(persona?.content ?? '');
  const { toast } = useToast();

  const isEditing = !!persona;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !content.trim()) return;

    onSave({
      id: persona?.id ?? crypto.randomUUID(),
      name: name.trim(),
      type,
      content: content.trim(),
      project_id: persona?.project_id,
    });

    toast(
      isEditing ? 'Persona updated' : 'Persona created',
      'success'
    );

    if (!isEditing) {
      setName('');
      setType('secondary');
      setContent('');
    }
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} className="max-w-2xl">
      <DialogClose onClose={onClose} />
      <DialogHeader>
        <DialogTitle>{isEditing ? 'Edit Persona' : 'Create Persona'}</DialogTitle>
      </DialogHeader>
      <form onSubmit={handleSubmit}>
        <DialogContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Persona Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Finance Director"
              required
            />
            <Select
              label="Type"
              value={type}
              onChange={(e) => setType(e.target.value as 'icp' | 'secondary')}
            >
              <option value="icp">ICP (Ideal Customer)</option>
              <option value="secondary">Secondary</option>
            </Select>
          </div>
          <div>
            <label className="block text-body-sm font-sans font-medium text-cream-800 mb-1.5">
              Persona Content (Markdown)
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Describe this persona in detail. Use markdown formatting..."
              rows={12}
              required
              className="w-full px-3 py-2 bg-white border border-[var(--border-default)] rounded-md font-body text-body text-cream-900 placeholder:text-cream-600 focus:outline-none focus:ring-2 focus:ring-terracotta-400/20 focus:border-terracotta-400 resize-y"
            />
          </div>
        </DialogContent>
        <DialogFooter>
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={!name.trim() || !content.trim()}>
            {isEditing ? 'Save Changes' : 'Create Persona'}
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
