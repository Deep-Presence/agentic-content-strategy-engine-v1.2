'use client';

import { useState } from 'react';
import { GitCompare } from 'lucide-react';
import { cn } from '@/lib/utils/cn';

interface DiffToggleProps {
  previousContent: string;
  currentContent: string;
  className?: string;
}

function computeLineDiff(previous: string, current: string) {
  const prevLines = previous.split('\n');
  const currLines = current.split('\n');
  const diff: Array<{ type: 'added' | 'removed' | 'unchanged'; text: string }> = [];

  const prevSet = new Set(prevLines);
  const currSet = new Set(currLines);

  // Simple line-by-line diff
  const maxLen = Math.max(prevLines.length, currLines.length);
  for (let i = 0; i < maxLen; i++) {
    const prevLine = prevLines[i];
    const currLine = currLines[i];

    if (prevLine === currLine) {
      if (prevLine !== undefined) {
        diff.push({ type: 'unchanged', text: prevLine });
      }
    } else {
      if (prevLine !== undefined && !currSet.has(prevLine)) {
        diff.push({ type: 'removed', text: prevLine });
      }
      if (currLine !== undefined && !prevSet.has(currLine)) {
        diff.push({ type: 'added', text: currLine });
      }
      if (prevLine !== undefined && currSet.has(prevLine)) {
        diff.push({ type: 'unchanged', text: prevLine });
      }
      if (currLine !== undefined && prevSet.has(currLine) && currLine !== prevLine) {
        diff.push({ type: 'unchanged', text: currLine });
      }
    }
  }

  return diff;
}

export function DiffToggle({ previousContent, currentContent, className }: DiffToggleProps) {
  const [showDiff, setShowDiff] = useState(false);

  if (!showDiff) {
    return (
      <button
        onClick={() => setShowDiff(true)}
        className={cn(
          'flex items-center gap-1.5 px-3 py-1.5 text-body-sm font-sans text-cream-700 hover:text-cream-900 hover:bg-cream-200 rounded-md transition-colors',
          className
        )}
      >
        <GitCompare className="h-4 w-4" />
        Show Diff
      </button>
    );
  }

  const diff = computeLineDiff(previousContent, currentContent);

  return (
    <div className={cn('space-y-2', className)}>
      <button
        onClick={() => setShowDiff(false)}
        className="flex items-center gap-1.5 px-3 py-1.5 text-body-sm font-sans text-sage-400 hover:text-sage-500 hover:bg-sage-50 rounded-md transition-colors"
      >
        <GitCompare className="h-4 w-4" />
        Hide Diff
      </button>

      {/* MVP: Split view */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <h4 className="text-caption font-sans font-semibold text-cream-700 uppercase tracking-wider">
            Previous Version
          </h4>
          <div className="border border-[var(--border-default)] rounded-md bg-white p-4 max-h-[500px] overflow-y-auto">
            <pre className="text-body-sm font-body text-cream-800 whitespace-pre-wrap">
              {previousContent || 'No previous version available.'}
            </pre>
          </div>
        </div>

        <div className="space-y-1">
          <h4 className="text-caption font-sans font-semibold text-cream-700 uppercase tracking-wider">
            Current Version
          </h4>
          <div className="border border-[var(--border-default)] rounded-md bg-white p-4 max-h-[500px] overflow-y-auto">
            {diff.length > 0 ? (
              <div className="space-y-0">
                {diff.map((line, idx) => (
                  <div
                    key={idx}
                    className={cn(
                      'text-body-sm font-body px-1 -mx-1',
                      line.type === 'added' && 'bg-sage-50 text-sage-500',
                      line.type === 'removed' && 'bg-error/10 text-error line-through',
                      line.type === 'unchanged' && 'text-cream-800'
                    )}
                  >
                    <span className="text-caption font-mono mr-2 text-cream-500">
                      {line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' '}
                    </span>
                    {line.text || '\u00A0'}
                  </div>
                ))}
              </div>
            ) : (
              <pre className="text-body-sm font-body text-cream-800 whitespace-pre-wrap">
                {currentContent}
              </pre>
            )}
          </div>
        </div>
      </div>
      {/* TODO: upgrade to inline diff */}
    </div>
  );
}
