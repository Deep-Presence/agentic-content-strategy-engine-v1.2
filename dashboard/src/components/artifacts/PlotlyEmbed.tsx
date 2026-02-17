"use client";

import { Expand } from "lucide-react";
import { useArtifactStore } from "@/stores/artifactStore";
import { VIZ_LABELS } from "@/lib/constants";

interface PlotlyEmbedProps {
  url: string;
  filename: string;
}

export function PlotlyEmbed({ url, filename }: PlotlyEmbedProps) {
  const { open } = useArtifactStore();

  const label = VIZ_LABELS[filename] || filename.replace(/_/g, " ").replace(/\.html$/, "");

  const handleExpand = () => {
    open({
      kind: "visualization",
      title: label,
      htmlUrl: url,
    });
  };

  return (
    <div className="group relative rounded-xl border border-canvas-muted bg-canvas overflow-hidden">
      {/* Title bar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-canvas-muted bg-canvas-subtle">
        <span className="font-mono text-[0.6875rem] text-ink-secondary truncate">
          {label}
        </span>
        <button
          onClick={handleExpand}
          className="p-1 rounded-md opacity-0 group-hover:opacity-100 hover:bg-canvas-muted text-ink-tertiary hover:text-ink transition-all"
          title="Expand"
        >
          <Expand size={14} />
        </button>
      </div>

      {/* Iframe */}
      <div className="aspect-[4/3]">
        <iframe
          src={url}
          sandbox="allow-scripts allow-same-origin"
          className="w-full h-full border-0"
          title={label}
          loading="lazy"
        />
      </div>
    </div>
  );
}
