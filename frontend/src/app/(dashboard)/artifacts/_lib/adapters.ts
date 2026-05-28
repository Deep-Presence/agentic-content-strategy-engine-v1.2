/**
 * Thin adapters: API responses → frontend types.
 */

import type { KBDocument } from '@/types';
import type { KBDocType, KBHealthResponseAPI } from './types';

export function buildKBDocument(
  docType: KBDocType,
  content: string,
  health: KBHealthResponseAPI | null,
): KBDocument {
  const docHealth = health?.doc_health?.[docType];

  return {
    id: `${docType}-v${docHealth?.current_version ?? 1}`,
    type: docType,
    client: health?.slug ?? '',
    version: `v${docHealth?.current_version ?? 1}`,
    markdown: content,
    lastUpdated: docHealth?.last_updated ?? new Date().toISOString(),
    wordCount: content.split(/\s+/).filter(Boolean).length,
  };
}
