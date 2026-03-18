'use client';

import { SWRConfig } from 'swr';
import { swrFetcher } from './swr-fetcher';

export function SWRProvider({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig
      value={{
        fetcher: swrFetcher,
        dedupingInterval: 5000,
        revalidateOnFocus: false,
        revalidateOnReconnect: true,
        shouldRetryOnError: true,
        errorRetryCount: 2,
        onErrorRetry: (error, _key, _config, revalidate, { retryCount }) => {
          // Don't retry on 4xx errors (except 408 Request Timeout / 429 Too Many Requests)
          const status = (error as { status?: number })?.status;
          if (status && status >= 400 && status < 500 && status !== 408 && status !== 429) return;
          if (retryCount >= 2) return;
          setTimeout(() => revalidate({ retryCount }), 3000);
        },
      }}
    >
      {children}
    </SWRConfig>
  );
}
