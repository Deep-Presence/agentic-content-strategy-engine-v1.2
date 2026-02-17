"use client";

import { useState, useEffect } from "react";
import { FileText, Image, Code, Eye, FolderOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  listCompanies,
  listArtifacts,
  getArtifactContent,
  getArtifactUrl,
} from "@/lib/api";
import { useArtifactStore } from "@/stores/artifactStore";
import {
  VALID_ARTIFACT_TYPES,
  ARTIFACT_TYPE_LABELS,
} from "@/lib/constants";
import type { ArtifactFile } from "@/types/api";

function getFileIcon(name: string) {
  if (name.endsWith(".html")) return Image;
  if (name.endsWith(".json")) return Code;
  return FileText;
}

export default function ArtifactsPage() {
  const { open } = useArtifactStore();

  const [companies, setCompanies] = useState<string[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<string>(VALID_ARTIFACT_TYPES[0]);
  const [files, setFiles] = useState<ArtifactFile[]>([]);
  const [isLoadingCompanies, setIsLoadingCompanies] = useState(true);
  const [isLoadingFiles, setIsLoadingFiles] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch companies on mount
  useEffect(() => {
    setIsLoadingCompanies(true);
    listCompanies()
      .then((res) => {
        setCompanies(res.companies);
        if (res.companies.length > 0) {
          setSelectedCompany(res.companies[0]);
        }
      })
      .catch(() => setError("Failed to load companies"))
      .finally(() => setIsLoadingCompanies(false));
  }, []);

  // Fetch files when company or type changes
  useEffect(() => {
    if (!selectedCompany) {
      setFiles([]);
      return;
    }

    setIsLoadingFiles(true);
    setError(null);
    listArtifacts(selectedType, selectedCompany)
      .then((res) => setFiles(res.files))
      .catch(() => {
        setFiles([]);
        setError(null); // Don't show error for empty types
      })
      .finally(() => setIsLoadingFiles(false));
  }, [selectedCompany, selectedType]);

  const handleViewFile = async (file: ArtifactFile) => {
    if (!selectedCompany) return;

    const filename = file.name;

    if (filename.endsWith(".html")) {
      open({
        kind: "visualization",
        title: filename,
        htmlUrl: getArtifactUrl(selectedType, selectedCompany, filename),
      });
      return;
    }

    try {
      const content = await getArtifactContent(
        selectedType,
        selectedCompany,
        filename,
      );
      if (filename.endsWith(".json")) {
        open({ kind: "json", title: filename, content });
      } else {
        open({ kind: "markdown", title: filename, content });
      }
    } catch {
      open({ kind: "markdown", title: filename, content: "Failed to load file." });
    }
  };

  return (
    <div>
      <h1 className="font-display text-[2.25rem] text-ink tracking-tight leading-tight">
        Artifacts
      </h1>
      <p className="text-ink-secondary mt-2 text-[0.9375rem]">
        Browse all pipeline outputs by company and type.
      </p>

      <div className="mt-8 flex gap-8">
        {/* Left: Company selector */}
        <div className="w-48 flex-shrink-0">
          <p className="font-mono text-[0.75rem] text-ink-secondary uppercase tracking-wider mb-3">
            Company
          </p>
          {isLoadingCompanies ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-9 rounded-lg bg-canvas-muted animate-pulse"
                />
              ))}
            </div>
          ) : companies.length === 0 ? (
            <p className="font-body text-[0.8125rem] text-ink-tertiary">
              No companies found.
            </p>
          ) : (
            <div className="space-y-1">
              {companies.map((c) => (
                <button
                  key={c}
                  onClick={() => setSelectedCompany(c)}
                  className={cn(
                    "w-full text-left px-3 py-2 rounded-lg font-body text-[0.875rem] transition-colors",
                    selectedCompany === c
                      ? "bg-terracotta-50 text-terracotta-700 font-medium"
                      : "text-ink-secondary hover:text-ink hover:bg-canvas-subtle",
                  )}
                >
                  {c}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right: Type tabs + file list */}
        <div className="flex-1 min-w-0">
          {/* Type tabs */}
          <div className="flex gap-1 border-b border-canvas-muted pb-px mb-6">
            {VALID_ARTIFACT_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => setSelectedType(t)}
                className={cn(
                  "px-3 py-2 rounded-t-lg font-mono text-[0.75rem] transition-colors -mb-px",
                  selectedType === t
                    ? "bg-canvas border border-canvas-muted border-b-canvas text-terracotta-600 font-medium"
                    : "text-ink-tertiary hover:text-ink",
                )}
              >
                {ARTIFACT_TYPE_LABELS[t] || t}
              </button>
            ))}
          </div>

          {/* File list */}
          {error && (
            <div className="rounded-xl border border-status-failed/20 bg-red-50 p-4 text-center">
              <p className="font-mono text-[0.8125rem] text-status-failed">
                {error}
              </p>
            </div>
          )}

          {!selectedCompany && (
            <div className="rounded-xl border border-canvas-muted bg-canvas-subtle p-12 text-center">
              <p className="font-body text-[0.875rem] text-ink-tertiary">
                Select a company to browse artifacts.
              </p>
            </div>
          )}

          {selectedCompany && isLoadingFiles && (
            <div className="space-y-2">
              {[1, 2, 3, 4].map((i) => (
                <div
                  key={i}
                  className="h-14 rounded-xl bg-canvas-muted animate-pulse"
                />
              ))}
            </div>
          )}

          {selectedCompany && !isLoadingFiles && files.length === 0 && !error && (
            <div className="rounded-xl border border-canvas-muted bg-canvas-subtle p-12 text-center">
              <FolderOpen
                size={32}
                className="mx-auto text-ink-tertiary mb-3"
              />
              <p className="font-body text-[0.875rem] text-ink-tertiary">
                No {ARTIFACT_TYPE_LABELS[selectedType]?.toLowerCase() || selectedType} artifacts for{" "}
                <span className="font-medium text-ink-secondary">
                  {selectedCompany}
                </span>
                .
              </p>
            </div>
          )}

          {selectedCompany && !isLoadingFiles && files.length > 0 && (
            <div className="space-y-2">
              {files.map((f) => {
                const Icon = getFileIcon(f.name);
                return (
                  <button
                    key={f.name}
                    onClick={() => handleViewFile(f)}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-canvas-muted bg-canvas hover:bg-canvas-subtle transition-colors text-left group"
                  >
                    <Icon
                      size={18}
                      className="text-terracotta-500 flex-shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="font-mono text-[0.8125rem] text-ink truncate">
                        {f.name}
                      </p>
                      <p className="font-mono text-[0.6875rem] text-ink-tertiary">
                        {f.size < 1024
                          ? `${f.size} B`
                          : `${(f.size / 1024).toFixed(1)} KB`}
                      </p>
                    </div>
                    <Eye
                      size={16}
                      className="text-ink-tertiary opacity-0 group-hover:opacity-100 transition-opacity"
                    />
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
