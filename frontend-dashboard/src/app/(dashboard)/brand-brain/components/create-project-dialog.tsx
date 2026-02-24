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
import { Button } from '@/components/ui/button';
import { useBrandStore } from '@/stores/brand-store';
import { useToast } from '@/components/ui/toast';

interface CreateProjectDialogProps {
  open: boolean;
  onClose: () => void;
}

export function CreateProjectDialog({ open, onClose }: CreateProjectDialogProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const addProject = useBrandStore((s) => s.addProject);
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setSaving(true);
    try {
      const project = {
        id: crypto.randomUUID(),
        name: name.trim(),
        slug: name.trim().toLowerCase().replace(/\s+/g, '-'),
        description: description.trim() || undefined,
        personas: [],
        knowledge_docs: [],
        created_at: new Date().toISOString(),
      };
      addProject(project);
      toast('Project created successfully', 'success');
      setName('');
      setDescription('');
      onClose();
    } catch {
      toast('Failed to create project', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogClose onClose={onClose} />
      <DialogHeader>
        <DialogTitle>New Project</DialogTitle>
      </DialogHeader>
      <form onSubmit={handleSubmit}>
        <DialogContent className="space-y-4">
          <Input
            label="Project Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Webflow Enterprise"
            required
          />
          <div>
            <label className="block text-body-sm font-sans font-medium text-cream-800 mb-1.5">
              Description (optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of this product or project"
              rows={3}
              className="w-full px-3 py-2 bg-white border border-[var(--border-default)] rounded-md font-body text-body text-cream-900 placeholder:text-cream-600 focus:outline-none focus:ring-2 focus:ring-terracotta-400/20 focus:border-terracotta-400 resize-none"
            />
          </div>
        </DialogContent>
        <DialogFooter>
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={!name.trim() || saving}>
            {saving ? 'Creating...' : 'Create Project'}
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
