'use client';

import { useState, useEffect, useCallback } from 'react';
import { artifacts, type ArtifactType } from '@/lib/api/artifacts';

interface UseCompaniesResult {
  companies: string[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useCompanies(): UseCompaniesResult {
  const [companies, setCompanies] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCompanies = useCallback(async () => {
    try {
      const result = await artifacts.listCompanies();
      setCompanies(result.companies);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch companies');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCompanies();
  }, [fetchCompanies]);

  return { companies, loading, error, refresh: fetchCompanies };
}

interface UseArtifactFilesResult {
  files: string[];
  loading: boolean;
  error: string | null;
}

export function useArtifactFiles(type: ArtifactType, slug: string): UseArtifactFilesResult {
  const [files, setFiles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;

    let cancelled = false;
    setLoading(true);

    artifacts
      .listFiles(type, slug)
      .then((result) => {
        if (!cancelled) {
          setFiles(result.files);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to fetch files');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [type, slug]);

  return { files, loading, error };
}

interface UseArtifactContentResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useArtifactContent<T = unknown>(
  type: ArtifactType,
  slug: string,
  filename: string
): UseArtifactContentResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug || !filename) return;

    let cancelled = false;
    setLoading(true);

    artifacts
      .getContent<T>(type, slug, filename)
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to fetch content');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [type, slug, filename]);

  return { data, loading, error };
}
