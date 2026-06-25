'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  getDefaultWebflowCollectionId,
  getEnabledWebflowCollections,
  isWebflowConfigured,
} from '../../settings/_lib/webflow-utils';
import type { CMSConnectionInfoAPI } from '../../settings/_lib/types';
import { fetchCMSConnectionForPublish } from '../_lib/api';

export interface WebflowPublishTarget {
  collectionId: string;
  label: string;
}

interface UseCMSConnectionReturn {
  connection: CMSConnectionInfoAPI | null;
  isLoading: boolean;
  cmsProvider: string | null;
  webflowPublishTargets: WebflowPublishTarget[];
  defaultWebflowCollectionId: string;
  canPublishToCMS: boolean;
}

export function useCMSConnection(): UseCMSConnectionReturn {
  const [connection, setConnection] = useState<CMSConnectionInfoAPI | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      setIsLoading(true);
      try {
        const result = await fetchCMSConnectionForPublish(controller.signal);
        if (!controller.signal.aborted) {
          setConnection(result as CMSConnectionInfoAPI | null);
        }
      } catch {
        if (!controller.signal.aborted) {
          setConnection(null);
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    })();
    return () => controller.abort();
  }, []);

  const cmsProvider = connection?.is_active ? connection.provider : null;

  const webflowPublishTargets = useMemo(() => {
    if (cmsProvider !== 'webflow' || !isWebflowConfigured(connection)) return [];
    return getEnabledWebflowCollections(connection).map((item) => ({
      collectionId: item.collection_id,
      label: item.display_name || item.collection_slug || item.collection_id,
    }));
  }, [cmsProvider, connection]);

  const defaultWebflowCollectionId = useMemo(
    () => (cmsProvider === 'webflow' ? getDefaultWebflowCollectionId(connection) : ''),
    [cmsProvider, connection],
  );

  const canPublishToCMS = cmsProvider === 'wordpress'
    || (cmsProvider === 'webflow' && isWebflowConfigured(connection));

  return {
    connection,
    isLoading,
    cmsProvider,
    webflowPublishTargets,
    defaultWebflowCollectionId,
    canPublishToCMS,
  };
}
