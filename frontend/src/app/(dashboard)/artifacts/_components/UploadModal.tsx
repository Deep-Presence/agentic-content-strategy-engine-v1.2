'use client';

import { useState, useRef, useCallback } from 'react';
import { Button } from '@/components/ui';
import { Upload, X, FileText, CheckCircle, AlertCircle, Globe } from 'lucide-react';
import { uploadArtifact } from '../_lib/api';

interface UploadModalProps {
  open: boolean;
  onClose: () => void;
  artifactType: string;
  slug: string;
  /** Sub-directory within artifact type (e.g. "company_overview", "guide", persona_id) */
  subPath?: string;
  onUploadComplete?: () => void;
}

export function UploadModal({ open, onClose, artifactType, slug, subPath, onUploadComplete }: UploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const ALLOWED_EXTENSIONS = ['.md', '.txt', '.pdf'];

  const reset = useCallback(() => {
    setFile(null);
    setResult(null);
    setUploading(false);
  }, []);

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleFile = (f: File) => {
    setResult(null);
    const ext = f.name.substring(f.name.lastIndexOf('.')).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setResult({ success: false, message: `Unsupported file type: ${ext}. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}` });
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      setResult({ success: false, message: 'File too large. Max 10 MB.' });
      return;
    }
    setFile(f);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setResult(null);
    try {
      const res = await uploadArtifact(artifactType, slug, file, subPath);
      setResult({ success: true, message: `Uploaded as ${res.filename}` });
      onUploadComplete?.();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setResult({ success: false, message: msg });
    } finally {
      setUploading(false);
    }
  };

  if (!open) return null;

  const artifactLabel = artifactType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-[2px]"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-[520px] bg-surface border border-border rounded-lg overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-2">
          <div />
          <button
            onClick={handleClose}
            className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-bg text-text-tertiary hover:text-text-primary transition-colors cursor-pointer"
          >
            <X size={16} strokeWidth={1.5} />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 pb-6 text-center">
          {/* Icon */}
          <div className="w-14 h-14 rounded-full bg-accent-subtle mx-auto mb-4 flex items-center justify-center">
            <Globe size={28} strokeWidth={1.5} className="text-accent" />
          </div>

          <h2 className="text-[18px] font-semibold text-text-primary mb-1.5">
            Upload to {artifactLabel}
          </h2>
          <p className="text-[13px] text-text-secondary mb-6 max-w-[380px] mx-auto leading-[1.6]">
            Upload a replacement document. It will be stored alongside existing versions.
          </p>

          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            className={`border-2 border-dashed rounded-md p-8 mb-4 transition-colors cursor-pointer ${
              dragOver
                ? 'border-accent bg-accent-subtle/50'
                : 'border-border hover:border-border-strong'
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".md,.txt,.pdf"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
                e.target.value = '';
              }}
            />
            {file ? (
              <div className="flex items-center justify-center gap-3">
                <FileText size={20} strokeWidth={1.5} className="text-accent" />
                <div className="text-left">
                  <p className="text-[13px] font-medium text-text-primary">{file.name}</p>
                  <p className="text-[11px] text-text-tertiary">{(file.size / 1024).toFixed(1)} KB</p>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); setFile(null); setResult(null); }}
                  className="ml-2 text-text-tertiary hover:text-text-primary cursor-pointer"
                >
                  <X size={14} strokeWidth={1.5} />
                </button>
              </div>
            ) : (
              <>
                <Upload size={24} strokeWidth={1.5} className="text-text-tertiary mx-auto mb-2" />
                <p className="text-[13px] font-medium text-text-secondary">Upload document</p>
                <p className="text-[11px] text-text-tertiary mt-1">
                  Drag & drop or click to browse
                </p>
              </>
            )}
          </div>

          {/* Supported formats */}
          <div className="flex items-center justify-center gap-3 mb-5 text-[11px] text-text-tertiary">
            <span>Supported:</span>
            {['MD', 'TXT', 'PDF'].map((fmt) => (
              <span key={fmt} className="px-2 py-0.5 border border-border rounded-sm text-text-secondary font-medium">
                {fmt}
              </span>
            ))}
          </div>

          {/* Result message */}
          {result && (
            <div className={`flex items-center gap-2 px-3 py-2 rounded-md mb-4 text-[12px] ${
              result.success
                ? 'bg-success-subtle border border-success/20 text-success'
                : 'bg-error-subtle border border-error/20 text-error'
            }`}>
              {result.success
                ? <CheckCircle size={14} strokeWidth={1.5} />
                : <AlertCircle size={14} strokeWidth={1.5} />
              }
              <span>{result.message}</span>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-3 justify-center">
            <Button variant="secondary" onClick={handleClose}>
              Cancel
            </Button>
            {result?.success ? (
              <Button variant="primary" onClick={handleClose}>
                Done
              </Button>
            ) : (
              <Button
                variant="primary"
                onClick={handleUpload}
                disabled={!file || uploading}
              >
                {uploading ? 'Uploading...' : 'Upload'}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
