'use client';

import { useState, useRef, useEffect } from 'react';
import { ChevronDown, Upload } from 'lucide-react';
import type { VersionEntry } from '../_lib/types';

interface VersionHistoryProps {
  versions: VersionEntry[];
  /** filePath of the actively selected entry */
  activeFilePath?: string;
  onSelectVersion: (entry: VersionEntry) => void;
}

export function VersionHistory({ versions, activeFilePath, onSelectVersion }: VersionHistoryProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Default to the first entry (highest version or latest)
  const selected = activeFilePath ?? versions[0]?.filePath;

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  if (versions.length === 0) return null;

  const selectedEntry = versions.find((v) => v.filePath === selected);

  return (
    <div className="border border-border rounded-md bg-surface p-4">
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary mb-3">
        Version History
      </div>
      <div ref={ref} className="relative">
        {/* Dropdown trigger */}
        <button
          onClick={() => setOpen(!open)}
          className="w-full flex items-center justify-between px-2.5 py-2 rounded-md border border-border bg-bg text-[12px] hover:border-border-strong transition-colors cursor-pointer"
        >
          <span className="font-medium text-text-primary truncate">
            {selectedEntry?.isUpload && <Upload size={10} strokeWidth={1.5} className="inline mr-1 text-text-tertiary" />}
            {selectedEntry?.label ?? 'Select version'}
          </span>
          <ChevronDown
            size={13}
            strokeWidth={1.5}
            className={`text-text-tertiary transition-transform flex-shrink-0 ml-1 ${open ? 'rotate-180' : ''}`}
          />
        </button>

        {/* Dropdown menu */}
        {open && (
          <div className="absolute z-20 left-0 right-0 mt-1 border border-border rounded-md bg-surface py-1 shadow-sm max-h-[240px] overflow-y-auto">
            {versions.map((v) => {
              const isActive = v.filePath === selected;
              const isLatest = v.filePath === versions[0]?.filePath && !v.isUpload;
              return (
                <button
                  key={v.filePath}
                  onClick={() => {
                    onSelectVersion(v);
                    setOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-2.5 py-2 text-[12px] transition-colors cursor-pointer ${
                    isActive
                      ? 'bg-accent-subtle text-accent font-medium'
                      : 'text-text-primary hover:bg-bg'
                  }`}
                >
                  <span className="truncate flex items-center gap-1.5">
                    {v.isUpload && <Upload size={10} strokeWidth={1.5} className="text-text-tertiary flex-shrink-0" />}
                    {v.label}
                  </span>
                  {isLatest && (
                    <span className="text-[9px] font-semibold uppercase tracking-wide text-text-tertiary flex-shrink-0 ml-1">
                      Latest
                    </span>
                  )}
                  {v.isUpload && (
                    <span className="text-[9px] font-semibold uppercase tracking-wide text-text-tertiary flex-shrink-0 ml-1">
                      Upload
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
