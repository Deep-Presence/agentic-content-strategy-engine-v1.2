'use client';

import { useState } from 'react';
import { Check, Pencil, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogHeader, DialogTitle, DialogContent, DialogFooter, DialogClose } from '@/components/ui/dialog';
import { cn } from '@/lib/utils/cn';

interface ApprovalBarProps {
  onApprove: () => void;
  onEdit: (notes: string) => void;
  onReject: () => void;
  loading?: boolean;
  className?: string;
}

export function ApprovalBar({ onApprove, onEdit, onReject, loading = false, className }: ApprovalBarProps) {
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [editNotes, setEditNotes] = useState('');

  function handleEditSubmit() {
    if (!editNotes.trim()) return;
    onEdit(editNotes.trim());
    setEditDialogOpen(false);
    setEditNotes('');
  }

  function handleRejectConfirm() {
    onReject();
    setRejectDialogOpen(false);
  }

  return (
    <>
      <div className={cn(
        'flex items-center justify-between px-6 py-3 bg-white border-t border-[var(--border-default)]',
        className
      )}>
        <p className="text-body-sm font-sans text-cream-600">
          Review this content and take action.
        </p>
        <div className="flex items-center gap-3">
          <Button
            variant="danger"
            size="md"
            onClick={() => setRejectDialogOpen(true)}
            disabled={loading}
          >
            <X className="h-4 w-4" />
            Reject
          </Button>
          <Button
            variant="secondary"
            size="md"
            onClick={() => setEditDialogOpen(true)}
            disabled={loading}
          >
            <Pencil className="h-4 w-4" />
            Edit + Note
          </Button>
          <Button
            size="md"
            onClick={onApprove}
            disabled={loading}
            className="bg-sage-400 hover:bg-sage-500"
          >
            <Check className="h-4 w-4" />
            {loading ? 'Approving...' : 'Approve & Publish'}
          </Button>
        </div>
      </div>

      {/* Edit Notes Dialog */}
      <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)}>
        <DialogClose onClose={() => setEditDialogOpen(false)} />
        <DialogHeader>
          <DialogTitle>Edit Notes</DialogTitle>
        </DialogHeader>
        <DialogContent>
          <p className="text-body-sm font-sans text-cream-700 mb-3">
            Provide notes for the revision. The content will be sent back to workers for refinement.
          </p>
          <textarea
            value={editNotes}
            onChange={(e) => setEditNotes(e.target.value)}
            placeholder="Describe what changes are needed..."
            rows={4}
            className="w-full px-3 py-2 text-body font-body bg-white border border-[var(--border-default)] rounded-md text-cream-900 placeholder:text-cream-500 focus:border-sage-400 focus:ring-2 focus:ring-sage-400/20 outline-none resize-none"
          />
        </DialogContent>
        <DialogFooter>
          <Button variant="secondary" onClick={() => setEditDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleEditSubmit} disabled={!editNotes.trim()}>
            Submit Notes
          </Button>
        </DialogFooter>
      </Dialog>

      {/* Reject Confirmation Dialog */}
      <Dialog open={rejectDialogOpen} onClose={() => setRejectDialogOpen(false)}>
        <DialogClose onClose={() => setRejectDialogOpen(false)} />
        <DialogHeader>
          <DialogTitle>Reject Content</DialogTitle>
        </DialogHeader>
        <DialogContent>
          <p className="text-body font-body text-cream-800">
            Are you sure? This will save the content as a draft. It can be re-submitted for generation later.
          </p>
        </DialogContent>
        <DialogFooter>
          <Button variant="secondary" onClick={() => setRejectDialogOpen(false)}>Cancel</Button>
          <Button variant="danger" onClick={handleRejectConfirm}>
            Reject & Save Draft
          </Button>
        </DialogFooter>
      </Dialog>
    </>
  );
}
