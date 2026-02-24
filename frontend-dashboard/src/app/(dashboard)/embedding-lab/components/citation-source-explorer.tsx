'use client';

import { useState } from 'react';
import { CitationExplorer } from '@/components/charts/citation-explorer';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';
import type { PlatformData } from '../data/webflow-sample';

interface CitationSourceExplorerProps {
  data: PlatformData[];
  className?: string;
}

const PLATFORM_COLORS: Record<string, string> = {
  ChatGPT: '#6a9bcc',
  Claude: '#d97757',
  Perplexity: '#788c5d',
  Gemini: '#e8926d',
};

function CitationSourceExplorer({ data, className }: CitationSourceExplorerProps) {
  const [selectedPlatform, setSelectedPlatform] = useState<string | null>(null);

  const totalCitations = data.reduce((s, d) => s + d.totalCitations, 0);
  const selectedInfo = selectedPlatform ? data.find((d) => d.platform === selectedPlatform) : null;

  return (
    <div className={cn('space-y-6', className)}>
      {/* Platform cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {data.map((platform) => (
          <Card
            key={platform.platform}
            hoverable
            accent={selectedPlatform === platform.platform ? 'ocean' : 'none'}
            onClick={() =>
              setSelectedPlatform(
                selectedPlatform === platform.platform ? null : platform.platform,
              )
            }
          >
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="h-3 w-3 rounded-full"
                  style={{ backgroundColor: PLATFORM_COLORS[platform.platform] }}
                />
                <span className="text-body-sm font-sans font-semibold text-cream-950">
                  {platform.platform}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-caption font-sans">
                <div>
                  <span className="text-cream-600">Total</span>
                  <div className="text-body font-semibold tabular-nums text-cream-950">
                    {platform.totalCitations}
                  </div>
                </div>
                <div>
                  <span className="text-cream-600">Unique</span>
                  <div className="text-body font-semibold tabular-nums text-cream-950">
                    {platform.uniqueCitations}
                  </div>
                </div>
                <div>
                  <span className="text-cream-600">Avg Sim.</span>
                  <div className="text-body font-semibold tabular-nums text-ocean-400">
                    {platform.avgSimilarity.toFixed(2)}
                  </div>
                </div>
                <div>
                  <span className="text-cream-600">Top Domain</span>
                  <div className="text-body-sm font-medium text-cream-900 truncate">
                    {platform.topDomain}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Bar chart */}
      <Card>
        <CardHeader>
          <CardTitle>Citations by Platform</CardTitle>
          <CardDescription>
            {totalCitations} total citations across all platforms.
            Click a bar to filter.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CitationExplorer
            data={data.map((d) => ({
              platform: d.platform,
              totalCitations: d.totalCitations,
              uniqueCitations: d.uniqueCitations,
              avgSimilarity: d.avgSimilarity,
              topDomain: d.topDomain,
            }))}
            onPlatformClick={(platform) =>
              setSelectedPlatform(
                selectedPlatform === platform ? null : platform,
              )
            }
            height={250}
          />
        </CardContent>
      </Card>

      {/* Selected platform detail */}
      {selectedInfo && (
        <Card accent="ocean">
          <CardHeader>
            <div className="flex items-center gap-2">
              <span
                className="h-3 w-3 rounded-full"
                style={{ backgroundColor: PLATFORM_COLORS[selectedInfo.platform] }}
              />
              <CardTitle>{selectedInfo.platform} Detail</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-caption font-sans text-cream-600 uppercase tracking-wide">Total Citations</div>
                <div className="text-heading-3 font-sans font-semibold tabular-nums text-cream-950">{selectedInfo.totalCitations}</div>
              </div>
              <div>
                <div className="text-caption font-sans text-cream-600 uppercase tracking-wide">Unique Citations</div>
                <div className="text-heading-3 font-sans font-semibold tabular-nums text-cream-950">{selectedInfo.uniqueCitations}</div>
              </div>
              <div>
                <div className="text-caption font-sans text-cream-600 uppercase tracking-wide">Avg Similarity</div>
                <div className="text-heading-3 font-sans font-semibold tabular-nums text-ocean-400">{selectedInfo.avgSimilarity.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-caption font-sans text-cream-600 uppercase tracking-wide">Top Domain</div>
                <Badge variant="blue" className="mt-1">{selectedInfo.topDomain}</Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export { CitationSourceExplorer };
export type { CitationSourceExplorerProps };
