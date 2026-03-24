import { cn } from '@/lib/utils';

interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => React.ReactNode;
  className?: string;
}

interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  className?: string;
}

export function Table<T extends Record<string, unknown>>({ columns, data, onRowClick, className }: TableProps<T>) {
  return (
    <div className={cn('w-full overflow-x-auto', className)}>
      <table className="w-full border-collapse">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  'text-[11px] font-medium tracking-[0.06em] uppercase text-text-tertiary text-left',
                  'py-2 px-3 border-b border-border bg-transparent',
                  col.className
                )}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr
              key={i}
              onClick={() => onRowClick?.(row)}
              className={cn(
                'transition-colors duration-100 ease-out h-[40px]',
                onRowClick && 'cursor-pointer',
                'hover:bg-accent-subtle'
              )}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={cn(
                    'py-2 px-3 text-[13px] border-b border-border-subtle',
                    col.className
                  )}
                >
                  {col.render ? col.render(row) : String(row[col.key] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
