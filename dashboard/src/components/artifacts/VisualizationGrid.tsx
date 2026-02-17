"use client";

import { PlotlyEmbed } from "./PlotlyEmbed";

interface VisualizationGridProps {
  files: { name: string; url: string }[];
}

export function VisualizationGrid({ files }: VisualizationGridProps) {
  if (files.length === 0) {
    return (
      <div className="rounded-xl border border-canvas-muted bg-canvas-subtle p-8 text-center">
        <p className="font-mono text-[0.8125rem] text-ink-tertiary">
          No visualizations produced.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {files.map((f) => (
        <PlotlyEmbed key={f.name} url={f.url} filename={f.name} />
      ))}
    </div>
  );
}
