import type { KBDocument } from '@/types';
import fs from 'fs';
import path from 'path';

const KB_TYPES: Record<string, KBDocument['type']> = {
  company_overview: 'company_overview',
  brand_perception: 'brand_perception',
  competitor_registry: 'competitor_registry',
  customer_reviews: 'customer_reviews',
  weakness_analysis: 'weakness_analysis',
};

export function getKnowledgeBase(): KBDocument[] {
  const basePath = path.join(process.cwd(), 'data/result-draft/artifacts/knowledge_base/lovable');
  const docs: KBDocument[] = [];

  try {
    const dirs = fs.readdirSync(basePath).filter((d) => {
      const fullPath = path.join(basePath, d);
      return fs.statSync(fullPath).isDirectory() && !d.startsWith('_');
    });

    for (const dir of dirs) {
      const type = KB_TYPES[dir];
      if (!type) continue;

      // Find latest version
      const dirPath = path.join(basePath, dir);
      const files = fs.readdirSync(dirPath).filter((f) => f.endsWith('.md')).sort();
      const latestFile = files[files.length - 1];
      if (!latestFile) continue;

      const mdPath = path.join(dirPath, latestFile);
      const content = fs.readFileSync(mdPath, 'utf-8');
      const stats = fs.statSync(mdPath);
      const version = latestFile.replace('.md', '');
      const wordCount = content.split(/\s+/).length;

      docs.push({
        id: `${dir}-${version}`,
        type,
        client: 'lovable',
        version,
        markdown: content,
        lastUpdated: stats.mtime.toISOString(),
        wordCount,
      });
    }
  } catch {
    // Data not available
  }

  return docs;
}
