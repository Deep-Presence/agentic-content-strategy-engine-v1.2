'use client';

import { useState, useRef } from 'react';
import { Upload, File, X } from 'lucide-react';
import { cn } from '@/lib/utils/cn';

interface FileUploadZoneProps {
  onFileSelect: (file: File) => void;
  accept?: string;
  className?: string;
}

export function FileUploadZone({
  onFileSelect,
  accept = '.pdf,.doc,.docx,.txt,.md',
  className,
}: FileUploadZoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      setSelectedFile(file);
      onFileSelect(file);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      onFileSelect(file);
    }
  };

  const clearFile = () => {
    setSelectedFile(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={cn(
        'relative border-2 border-dashed rounded-md p-6 text-center cursor-pointer transition-colors',
        dragOver
          ? 'border-terracotta-400 bg-terracotta-50'
          : 'border-[var(--border-default)] bg-cream-100 hover:border-cream-500',
        className
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={handleChange}
        className="hidden"
      />
      {selectedFile ? (
        <div className="flex items-center justify-center gap-3">
          <File className="h-5 w-5 text-terracotta-400" />
          <span className="font-sans text-body-sm text-cream-800">
            {selectedFile.name}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              clearFile();
            }}
            className="p-1 hover:bg-cream-200 rounded transition-colors"
          >
            <X className="h-3.5 w-3.5 text-cream-600" />
          </button>
        </div>
      ) : (
        <>
          <Upload className="h-8 w-8 text-cream-500 mx-auto mb-2" />
          <p className="font-sans text-body-sm text-cream-700">
            Drag & drop a file here, or click to browse
          </p>
          <p className="font-sans text-caption text-cream-500 mt-1">
            PDF, DOC, TXT, or Markdown files
          </p>
        </>
      )}
    </div>
  );
}
