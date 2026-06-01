import type { CMSConnectionInfoAPI } from './types';

export interface WebflowCollectionConfigStored {
  collection_id: string;
  collection_slug?: string;
  display_name?: string;
  enabled?: boolean;
  is_default_publish_target?: boolean;
}

export function getWebflowCollections(
  connection: CMSConnectionInfoAPI | null,
): WebflowCollectionConfigStored[] {
  if (!connection || connection.provider !== 'webflow') return [];
  const raw = connection.provider_config?.collections;
  if (!Array.isArray(raw)) return [];
  return raw.filter((item): item is WebflowCollectionConfigStored => {
    return !!item && typeof item === 'object' && 'collection_id' in item;
  });
}

export function isWebflowConfigured(connection: CMSConnectionInfoAPI | null): boolean {
  return getWebflowCollections(connection).some((c) => c.enabled !== false && c.collection_id);
}

export function getEnabledWebflowCollections(
  connection: CMSConnectionInfoAPI | null,
): WebflowCollectionConfigStored[] {
  return getWebflowCollections(connection).filter((c) => c.enabled !== false && c.collection_id);
}

export function getDefaultWebflowCollectionId(
  connection: CMSConnectionInfoAPI | null,
): string {
  const enabled = getEnabledWebflowCollections(connection);
  const defaultFromConfig = connection?.provider_config?.default_collection_id;
  if (typeof defaultFromConfig === 'string' && defaultFromConfig) {
    return defaultFromConfig;
  }
  const marked = enabled.find((c) => c.is_default_publish_target);
  if (marked?.collection_id) return marked.collection_id;
  return enabled[0]?.collection_id ?? '';
}
