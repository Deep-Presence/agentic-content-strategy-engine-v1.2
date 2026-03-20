import { apiGet } from './client';

/**
 * SWR-compatible fetcher. Delegates to apiGet which handles
 * JWT injection, 401 redirects, and throws ApiError on failure.
 */
export const swrFetcher = <T>(path: string): Promise<T> => apiGet<T>(path);
