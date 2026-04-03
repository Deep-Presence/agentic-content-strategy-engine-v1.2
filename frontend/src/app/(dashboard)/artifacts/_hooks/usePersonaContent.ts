'use client';

import { useState, useEffect, useRef } from 'react';
import type { Persona } from '@/types';
import { ApiError } from '@/lib/api-client';
import { fetchPersonaContent } from '../_lib/api';
import { parsePersonaMarkdown } from '../_lib/parse-persona';

interface UsePersonaContentResult {
  persona: Persona | null;
  isLoading: boolean;
  error: string | null;
}

export function usePersonaContent(
  slug: string,
  personaId: string,
  version: number,
): UsePersonaContentResult {
  const [persona, setPersona] = useState<Persona | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!slug || !personaId) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setError(null);

    fetchPersonaContent(slug, personaId, version, controller.signal)
      .then((markdown) => {
        if (controller.signal.aborted) return;
        setPersona(parsePersonaMarkdown(markdown, personaId, slug, version));
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        if (err instanceof ApiError) {
          setError(err.detail);
        } else {
          setError('Unable to load persona content.');
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [slug, personaId, version]);

  return { persona, isLoading, error };
}
