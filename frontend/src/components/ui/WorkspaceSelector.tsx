'use client';

import { cn } from '@/lib/utils';
import { ChevronDown, Plus, Check } from 'lucide-react';
import { useWorkspaceStore, type Workspace } from '@/stores/workspace';
import { useState, useRef, useEffect } from 'react';

interface WorkspaceSelectorProps {
  className?: string;
  collapsed?: boolean;
}

function WorkspaceIcon({ color, size = 28 }: { color: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" className="flex-shrink-0">
      <rect x="2" y="10" width="14" height="14" rx="3.5" fill={color} opacity="0.35" />
      <rect x="10" y="4" width="14" height="14" rx="3.5" fill={color} opacity="0.75" />
    </svg>
  );
}

export function WorkspaceSelector({ className, collapsed = false }: WorkspaceSelectorProps) {
  const {
    workspaces,
    activeWorkspaceSlug,
    setActiveWorkspace,
    createWorkspace,
    isLoading,
  } = useWorkspaceStore();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDomain, setNewDomain] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const activeWorkspace = workspaces.find((w) => w.slug === activeWorkspaceSlug);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
        setCreating(false);
        setNewName('');
        setNewDomain('');
      }
    };
    if (open) {
      document.addEventListener('mousedown', handler);
    }
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  useEffect(() => {
    if (creating && inputRef.current) {
      inputRef.current.focus();
    }
  }, [creating]);

  const handleSelect = (workspace: Workspace) => {
    setActiveWorkspace(workspace.slug);
    setOpen(false);
  };

  const handleCreate = async () => {
    const name = newName.trim();
    const domain = newDomain.trim() || `${name.toLowerCase().replace(/\s+/g, '')}.com`;
    if (!name) return;
    await createWorkspace({ name, primary_domain: domain });
    setNewName('');
    setNewDomain('');
    setCreating(false);
    setOpen(false);
  };

  if (collapsed) {
    return (
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-center w-full cursor-pointer"
      >
        <WorkspaceIcon color={activeWorkspace?.color ?? '#5BA4C4'} size={24} />
      </button>
    );
  }

  return (
    <div ref={dropdownRef} className={cn('relative', className)}>
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center gap-2.5 w-full rounded-md px-2.5 py-2',
          'bg-surface-raised border border-border-strong',
          'hover:border-accent transition-colors duration-150 cursor-pointer',
        )}
      >
        <WorkspaceIcon color={activeWorkspace?.color ?? '#5BA4C4'} size={28} />
        <span className="flex-1 text-left text-[13px] font-medium text-text-primary truncate">
          {isLoading ? 'Loading workspaces…' : activeWorkspace?.name ?? 'Select workspace'}
        </span>
        <ChevronDown
          size={14}
          strokeWidth={1.5}
          className={cn(
            'text-text-tertiary transition-transform duration-150 flex-shrink-0',
            open && 'rotate-180'
          )}
        />
      </button>

      {open && (
        <div className="absolute top-full left-0 right-0 mt-1 z-50 rounded-md border border-border bg-surface-raised shadow-float overflow-hidden">
          <div className="py-1">
            {workspaces.map((ws) => (
              <button
                key={ws.id}
                onClick={() => handleSelect(ws)}
                className={cn(
                  'flex items-center gap-2.5 w-full px-2.5 py-2 text-left',
                  'hover:bg-accent-subtle transition-colors cursor-pointer',
                  ws.slug === activeWorkspaceSlug && 'bg-accent-subtle'
                )}
              >
                <WorkspaceIcon color={ws.color} size={22} />
                <span className="flex-1 text-[12px] font-medium text-text-primary truncate">
                  {ws.name}
                </span>
                {ws.slug === activeWorkspaceSlug && (
                  <Check size={14} strokeWidth={1.5} className="text-accent flex-shrink-0" />
                )}
              </button>
            ))}
          </div>

          <div className="border-t border-border" />

          {creating ? (
            <div className="p-2 space-y-2">
              <input
                ref={inputRef}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void handleCreate();
                  if (e.key === 'Escape') {
                    setCreating(false);
                    setNewName('');
                    setNewDomain('');
                  }
                }}
                placeholder="Workspace name..."
                className="w-full h-[30px] px-2 text-[12px] rounded-sm border border-border bg-bg text-text-primary placeholder:text-text-tertiary outline-none focus:border-accent"
              />
              <input
                value={newDomain}
                onChange={(e) => setNewDomain(e.target.value)}
                placeholder="Primary domain (optional)"
                className="w-full h-[30px] px-2 text-[12px] rounded-sm border border-border bg-bg text-text-primary placeholder:text-text-tertiary outline-none focus:border-accent"
              />
            </div>
          ) : (
            <button
              onClick={() => setCreating(true)}
              className={cn(
                'flex items-center justify-center gap-1.5 w-full px-2.5 py-2.5',
                'text-[12px] font-medium text-text-secondary',
                'hover:bg-accent-subtle hover:text-text-primary transition-colors cursor-pointer',
              )}
            >
              New <Plus size={14} strokeWidth={1.5} />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
