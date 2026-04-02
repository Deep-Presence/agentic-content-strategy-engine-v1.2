'use client';

import { useState } from 'react';
import { Badge, Button } from '@/components/ui';
import {
  Search,
  ChevronRight,
  Plus,
  Upload,
  Users,
  MoreVertical,
  Edit3,
  Share2,
  Trash2,
} from 'lucide-react';
import type { Persona } from '@/types';

interface PersonasListViewProps {
  personas: Persona[];
  onBack: () => void;
  onSelectPersona: (id: string) => void;
}

export function PersonasListView({ personas, onBack, onSelectPersona }: PersonasListViewProps) {
  const [search, setSearch] = useState('');
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const filtered = personas.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.title.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 mb-4 text-[12px]">
        <button onClick={onBack} className="text-text-secondary hover:text-accent cursor-pointer transition-colors">
          Brand Artifact
        </button>
        <ChevronRight size={11} strokeWidth={1.5} className="text-text-tertiary" />
        <span className="text-text-primary font-medium">Audience Personas</span>
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <h1 className="font-display text-[20px] font-semibold tracking-[-0.02em] text-text-primary">
            Audience Personas
          </h1>
          <p className="text-[13px] text-text-secondary mt-0.5">
            Manage your buyer personas. Click to view details.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary">
            <Upload size={13} strokeWidth={1.5} className="mr-1.5" />
            Import
          </Button>
          <Button variant="primary">
            <Plus size={13} strokeWidth={1.5} className="mr-1.5" />
            Add Persona
          </Button>
        </div>
      </div>

      {/* Search */}
      <div className="mb-4">
        <div className="relative w-[280px]">
          <Search size={14} strokeWidth={1.5} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
          <input
            type="text"
            placeholder="Search personas..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full h-[36px] pl-9 pr-3 text-[13px] border border-border rounded-md bg-surface text-text-primary outline-none focus:border-accent placeholder:text-text-tertiary"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-surface border border-border rounded-md overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-[1fr_140px_140px_100px_40px] gap-3 px-5 py-3 border-b border-border bg-bg">
          <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary">Name</div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary">Added By</div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary">Updated On</div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary">Version</div>
          <div />
        </div>

        {/* Rows */}
        {filtered.map(persona => (
          <div key={persona.id} className="relative grid grid-cols-[1fr_140px_140px_100px_40px] gap-3 px-5 py-3.5 border-b border-border-subtle hover:bg-bg transition-colors group last:border-b-0">
            {/* Name — clickable */}
            <button
              onClick={() => onSelectPersona(persona.id)}
              className="flex items-center gap-3 min-w-0 text-left cursor-pointer"
            >
              <div className="w-8 h-8 rounded-full bg-accent-subtle flex items-center justify-center text-[13px] font-semibold text-accent flex-shrink-0">
                {persona.name.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0">
                <div className="text-[14px] font-medium text-text-primary truncate group-hover:text-accent transition-colors">
                  {persona.name}
                </div>
                <div className="text-[11px] text-text-tertiary truncate">{persona.title}</div>
              </div>
            </button>

            {/* Added By */}
            <div className="flex items-center text-[13px] text-text-secondary">Pipeline AI</div>

            {/* Updated */}
            <div className="flex items-center text-[12px] text-text-tertiary">Mar 24, 2026</div>

            {/* Version */}
            <div className="flex items-center"><Badge variant="neutral">{persona.version}</Badge></div>

            {/* Actions Menu */}
            <div className="flex items-center justify-center relative">
              <button
                onClick={() => setOpenMenu(openMenu === persona.id ? null : persona.id)}
                className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-bg cursor-pointer transition-colors"
              >
                <MoreVertical size={14} strokeWidth={1.5} className="text-text-tertiary" />
              </button>

              {openMenu === persona.id && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setOpenMenu(null)} />
                  <div className="absolute right-0 top-8 z-20 w-[140px] bg-surface border border-border rounded-md py-1 shadow-sm">
                    <button
                      onClick={() => { onSelectPersona(persona.id); setOpenMenu(null); }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-[12px] text-text-primary hover:bg-bg cursor-pointer"
                    >
                      <Edit3 size={12} strokeWidth={1.5} /> Edit
                    </button>
                    <button className="w-full flex items-center gap-2 px-3 py-2 text-[12px] text-text-primary hover:bg-bg cursor-pointer">
                      <Share2 size={12} strokeWidth={1.5} /> Share
                    </button>
                    <div className="border-t border-border my-1" />
                    <button className="w-full flex items-center gap-2 px-3 py-2 text-[12px] text-error hover:bg-error-subtle cursor-pointer">
                      <Trash2 size={12} strokeWidth={1.5} /> Delete
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        ))}

        {filtered.length === 0 && (
          <div className="px-5 py-10 text-center text-[13px] text-text-tertiary">
            No personas found.
          </div>
        )}
      </div>
    </div>
  );
}
