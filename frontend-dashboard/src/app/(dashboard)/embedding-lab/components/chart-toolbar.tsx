'use client';

import { Download, ZoomIn, ZoomOut, Maximize2, Filter } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';

interface ChartToolbarProps {
  onExport?: () => void;
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onFitToScreen?: () => void;
  onFilterToggle?: () => void;
  showFilter?: boolean;
  className?: string;
}

function ChartToolbar({
  onExport,
  onZoomIn,
  onZoomOut,
  onFitToScreen,
  onFilterToggle,
  showFilter = true,
  className,
}: ChartToolbarProps) {
  return (
    <div className={cn('flex items-center gap-1', className)}>
      {onZoomIn && (
        <Button variant="ghost" size="icon" onClick={onZoomIn} title="Zoom in">
          <ZoomIn className="h-4 w-4" />
        </Button>
      )}
      {onZoomOut && (
        <Button variant="ghost" size="icon" onClick={onZoomOut} title="Zoom out">
          <ZoomOut className="h-4 w-4" />
        </Button>
      )}
      {onFitToScreen && (
        <Button variant="ghost" size="icon" onClick={onFitToScreen} title="Fit to screen">
          <Maximize2 className="h-4 w-4" />
        </Button>
      )}
      {showFilter && onFilterToggle && (
        <Button variant="ghost" size="icon" onClick={onFilterToggle} title="Toggle filters">
          <Filter className="h-4 w-4" />
        </Button>
      )}
      {onExport && (
        <Button variant="secondary" size="sm" onClick={onExport}>
          <Download className="h-3.5 w-3.5" />
          Export
        </Button>
      )}
    </div>
  );
}

export { ChartToolbar };
export type { ChartToolbarProps };
