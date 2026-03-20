'use client';

import { useState } from 'react';
import { Badge, Toast } from '@/components/ui';
import { ChevronDown, ChevronRight, Edit3, Save } from 'lucide-react';
import type { Persona } from '@/types';

interface PersonasTabProps {
  personas: Persona[];
}

export function PersonasTab({ personas }: PersonasTabProps) {
  const [expandedPersona, setExpandedPersona] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [editMode, setEditMode] = useState<string | null>(null);
  const [editedContent, setEditedContent] = useState<Record<string, string>>({});
  const [toastOpen, setToastOpen] = useState(false);

  const togglePersona = (id: string) => {
    setExpandedPersona(prev => prev === id ? null : id);
    setEditMode(null);
  };

  const toggleSection = (key: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const handleEdit = (personaId: string) => {
    setEditMode(prev => prev === personaId ? null : personaId);
  };

  const handleSave = () => {
    setEditMode(null);
    setToastOpen(true);
  };

  const handleContentChange = (key: string, value: string) => {
    setEditedContent(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div className="space-y-2">
      {personas.map(persona => {
        const isExpanded = expandedPersona === persona.id;
        const isEditing = editMode === persona.id;

        return (
          <div key={`${persona.client}-${persona.id}`} className="bg-surface border border-border rounded-md overflow-hidden">
            {/* Persona Header */}
            <button
              onClick={() => togglePersona(persona.id)}
              className="w-full flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-bg transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-accent-subtle flex items-center justify-center text-[13px] font-semibold text-accent">
                  {persona.name.charAt(0).toUpperCase()}
                </div>
                <div className="text-left">
                  <div className="text-[13px] font-medium text-text-primary">{persona.name}</div>
                  <div className="text-[11px] text-text-tertiary">{persona.title}</div>
                </div>
                <Badge variant="neutral">{persona.client}</Badge>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="info">{persona.version}</Badge>
                {isExpanded ? (
                  <ChevronDown size={14} strokeWidth={1.5} className="text-text-tertiary" />
                ) : (
                  <ChevronRight size={14} strokeWidth={1.5} className="text-text-tertiary" />
                )}
              </div>
            </button>

            {/* Expanded Content */}
            {isExpanded && (
              <div className="border-t border-border">
                {/* Edit Toggle */}
                <div className="flex items-center justify-end px-4 py-2 border-b border-border-subtle">
                  {isEditing ? (
                    <button
                      onClick={() => handleSave()}
                      className="inline-flex items-center gap-1 h-[26px] px-2 text-[11px] font-medium text-success bg-success-subtle border border-success/20 rounded-sm cursor-pointer"
                    >
                      <Save size={12} strokeWidth={1.5} />
                      Save
                    </button>
                  ) : (
                    <button
                      onClick={() => handleEdit(persona.id)}
                      className="inline-flex items-center gap-1 h-[26px] px-2 text-[11px] text-text-secondary border border-border rounded-sm cursor-pointer hover:border-border-strong"
                    >
                      <Edit3 size={12} strokeWidth={1.5} />
                      Edit
                    </button>
                  )}
                </div>

                {/* Sections */}
                <div className="divide-y divide-border-subtle">
                  {persona.sections.map((section, idx) => {
                    const sectionKey = `${persona.id}-${idx}`;
                    const isSectionExpanded = expandedSections.has(sectionKey);
                    const contentKey = `${persona.client}-${persona.id}-${idx}`;
                    const currentContent = editedContent[contentKey] ?? section.content;

                    return (
                      <div key={sectionKey}>
                        <button
                          onClick={() => toggleSection(sectionKey)}
                          className="w-full flex items-center justify-between px-4 py-2.5 cursor-pointer hover:bg-bg transition-colors"
                        >
                          <span className="text-[12px] font-medium text-text-primary">{section.title}</span>
                          {isSectionExpanded ? (
                            <ChevronDown size={12} strokeWidth={1.5} className="text-text-tertiary" />
                          ) : (
                            <ChevronRight size={12} strokeWidth={1.5} className="text-text-tertiary" />
                          )}
                        </button>
                        {isSectionExpanded && (
                          <div className="px-4 pb-3">
                            {isEditing ? (
                              <textarea
                                value={currentContent}
                                onChange={e => handleContentChange(contentKey, e.target.value)}
                                className="w-full min-h-[120px] p-3 text-[12px] text-text-secondary leading-[1.55] bg-bg border border-border rounded-md outline-none focus:border-accent resize-y font-mono"
                              />
                            ) : (
                              <div className="text-[12px] text-text-secondary leading-[1.55] whitespace-pre-wrap">
                                {currentContent}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        );
      })}

      <Toast open={toastOpen} onClose={() => setToastOpen(false)} variant="success" message="Changes saved locally" />
    </div>
  );
}
