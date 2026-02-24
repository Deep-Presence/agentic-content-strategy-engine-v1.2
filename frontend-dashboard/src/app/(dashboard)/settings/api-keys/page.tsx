'use client';

import { useState, useEffect } from 'react';
import { CheckCircle, XCircle, Key, RefreshCw } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/components/layout/page-header';
import { api } from '@/lib/api/client';
import type { ReadinessResponse } from '@/types/common';

const REQUIRED_KEYS = [
  { key: 'OPENAI_API_KEY', label: 'OpenAI', description: 'Used for embeddings and GPT queries' },
  { key: 'ANTHROPIC_API_KEY', label: 'Anthropic', description: 'Used for Claude queries and content generation' },
  { key: 'GOOGLE_API_KEY', label: 'Google', description: 'Used for Gemini platform searches' },
  { key: 'PERPLEXITY_API_KEY', label: 'Perplexity', description: 'Used for Perplexity platform searches' },
];

export default function ApiKeysSettingsPage() {
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [loading, setLoading] = useState(true);

  async function checkReadiness() {
    setLoading(true);
    try {
      const result = await api.get<ReadinessResponse>('/readiness');
      setReadiness(result);
    } catch {
      setReadiness(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    checkReadiness();
  }, []);

  return (
    <div className="space-y-8">
      <PageHeader
        title="API Keys"
        description="Configure the API keys required for pipeline operation"
        actions={
          <Button variant="secondary" size="sm" onClick={checkReadiness}>
            <RefreshCw className="h-4 w-4" />
            Check Status
          </Button>
        }
      />

      {/* Readiness Status */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>System Readiness</CardTitle>
            {loading ? (
              <Skeleton className="h-6 w-20" />
            ) : readiness?.ready ? (
              <Badge variant="green">Ready</Badge>
            ) : (
              <Badge variant="error">Not Ready</Badge>
            )}
          </div>
          <CardDescription>
            All API keys must be configured on the backend for pipelines to run
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {REQUIRED_KEYS.map((k) => (
                <Skeleton key={k.key} className="h-14 w-full" />
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              {REQUIRED_KEYS.map((keyInfo) => {
                const isMissing = readiness?.missing_keys?.includes(keyInfo.key);
                const isConfigured = readiness && !isMissing;

                return (
                  <div
                    key={keyInfo.key}
                    className="flex items-center justify-between p-3 rounded-md border border-[var(--border-default)]"
                  >
                    <div className="flex items-center gap-3">
                      <Key className="h-4 w-4 text-cream-600" />
                      <div>
                        <p className="text-body-sm font-sans font-medium text-cream-900">
                          {keyInfo.label}
                        </p>
                        <p className="text-caption text-cream-600">{keyInfo.description}</p>
                      </div>
                    </div>
                    {isConfigured ? (
                      <div className="flex items-center gap-1.5 text-sage-400">
                        <CheckCircle className="h-4 w-4" />
                        <span className="text-body-sm font-sans font-medium">Configured</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5 text-error">
                        <XCircle className="h-4 w-4" />
                        <span className="text-body-sm font-sans font-medium">Missing</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {!readiness && !loading && (
            <div className="p-4 bg-warning/10 rounded-md border border-warning/30 mt-4">
              <p className="text-body-sm font-sans text-cream-800">
                Could not connect to the backend. Make sure the API server is running on{' '}
                <code className="font-mono text-caption bg-cream-200 px-1 py-0.5 rounded">
                  localhost:8000
                </code>
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Configure Keys */}
      <Card>
        <CardHeader>
          <CardTitle>Configure Keys</CardTitle>
          <CardDescription>
            API keys are stored on the backend server. Update your .env file to configure them.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {REQUIRED_KEYS.map((keyInfo) => (
            <Input
              key={keyInfo.key}
              label={keyInfo.label + ' API Key'}
              type="password"
              placeholder={`Enter ${keyInfo.key}`}
              disabled
            />
          ))}
          <p className="text-caption text-cream-600">
            Key management through the UI is coming soon. For now, configure keys in your
            backend .env file.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
