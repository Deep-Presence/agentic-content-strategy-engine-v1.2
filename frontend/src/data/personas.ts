import type { Persona } from '@/types';
import fs from 'fs';
import path from 'path';

function parsePersonaMd(markdown: string, name: string, client: string, version: string): Persona {
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

  return {
    id: `${client}-${name}-${version}`,
    name: name.charAt(0).toUpperCase() + name.slice(1),
    title: titleMatch?.[1]?.trim() || name,
    client,
    version,
    sections,
  };
}

export function getPersonas(): Persona[] {
  const basePath = path.join(process.cwd(), 'data/artifacts/audience_personas');
  const personas: Persona[] = [];

  try {
    const clients = fs.readdirSync(basePath).filter((d) => {
      const fullPath = path.join(basePath, d);
      return fs.statSync(fullPath).isDirectory() && !d.startsWith('_');
    });

    for (const client of clients) {
      const clientPath = path.join(basePath, client);
      const dirs = fs.readdirSync(clientPath).filter((d) => {
        const fullPath = path.join(clientPath, d);
        return fs.statSync(fullPath).isDirectory() && !d.startsWith('_');
      });

      for (const dir of dirs) {
        const personaDir = path.join(clientPath, dir);
        const mdFiles = fs.readdirSync(personaDir).filter((f) => f.endsWith('.md')).sort();

        for (const mdFile of mdFiles) {
          const mdPath = path.join(personaDir, mdFile);
          const content = fs.readFileSync(mdPath, 'utf-8');
          const version = mdFile.replace('.md', '');
          personas.push(parsePersonaMd(content, dir, client, version));
        }
      }
    }
  } catch {
    // Data not available
  }

  return personas;
}
