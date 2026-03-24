import { cn } from '@/lib/utils';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  selected?: boolean;
  hoverable?: boolean;
}

export function Card({ selected, hoverable = true, className, children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        'bg-surface border border-border rounded-md p-4 transition-[border-color] duration-150 ease-out',
        hoverable && 'hover:border-border-strong',
        selected && 'border-accent bg-accent-subtle',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
