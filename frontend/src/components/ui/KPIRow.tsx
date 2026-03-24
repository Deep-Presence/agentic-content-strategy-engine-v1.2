import { cn } from '@/lib/utils';

interface KPICell {
  label: string;
  value: string | number;
  delta?: string;
  deltaType?: 'positive' | 'negative' | 'neutral';
}

interface KPIRowProps {
  cells: KPICell[];
  className?: string;
}

export function KPIRow({ cells, className }: KPIRowProps) {
  return (
    <div
      className={cn('grid gap-[1px] bg-border rounded-sm overflow-hidden', className)}
      style={{ gridTemplateColumns: `repeat(${cells.length}, 1fr)` }}
    >
      {cells.map((cell, i) => (
        <div key={i} className="bg-bg px-4 py-4">
          <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary leading-[1.4]">
            {cell.label}
          </p>
          <div className="flex items-baseline gap-2 mt-1.5">
            <p className="font-display text-[28px] font-semibold tracking-[-0.02em] text-text-primary">
              {cell.value}
            </p>
            {cell.delta && (
              <p className={cn(
                'text-[12px] font-medium',
                cell.deltaType === 'positive' && 'text-success',
                cell.deltaType === 'negative' && 'text-error',
                (!cell.deltaType || cell.deltaType === 'neutral') && 'text-text-tertiary',
              )}>
                {cell.delta}
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
