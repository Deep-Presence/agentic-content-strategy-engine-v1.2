'use client';

import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';
import { useWorkspaceStore } from '@/stores/workspace';

interface WorkspaceSelectorProps {
  className?: string;
}

export function WorkspaceSelector({ className }: WorkspaceSelectorProps) {
  const { companyName } = useWorkspaceStore();

  return (
    <button
      className={cn(
        'flex items-center gap-1 rounded-sm text-[13px] font-medium',
        'text-text-secondary hover:text-text-primary transition-colors cursor-pointer',
        className
      )}
    >
      {companyName}
      <ChevronDown size={12} strokeWidth={1.5} className="text-text-tertiary" />
    </button>
  );
}
