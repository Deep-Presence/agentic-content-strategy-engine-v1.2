/**
 * Pure parsing function for Persona markdown.
 * Extracted from frontend/src/data/personas.ts — no fs dependency.
 */

import type { Persona } from '@/types';

export function parsePersonaMarkdown(
  markdown: string,
  personaId: string,
  slug: string,
  version: number,
): Persona {
  const sections: { title: string; content: string }[] = [];
  const parts = markdown.split(/^## /m);

  for (const part of parts.slice(1)) {
    const lines = part.split('\n');
    const title = lines[0].trim();
    const content = lines.slice(1).join('\n').trim();
    sections.push({ title, content });
  }

  const titleSection = sections.find((s) => s.title.includes('Persona Title'));
  const titleMatch = titleSection?.content.match(/\*\*Persona Title:\*\*\s*(.*)/);

  // Derive display name from persona_id (e.g., "marcus" → "Marcus")
  const displayName = personaId
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');

  return {
    id: `${slug}-${personaId}-v${version}`,
    name: displayName,
    title: titleMatch?.[1]?.trim() || displayName,
    client: slug,
    version: `v${version}`,
    sections,
  };
}
