import { cn } from '@/lib/utils';
import { LocusLogo } from './LocusLogo';
import { Button } from './button';

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  className?: string;
}

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-16 px-4', className)}>
      <div className="text-text-tertiary mb-5">
        <LocusLogo variant="symbol" size={48} />
      </div>
      <h3 className="text-[20px] font-semibold text-text-primary mb-1.5">{title}</h3>
      {description && (
        <p className="text-[14px] text-text-secondary max-w-[360px] text-center leading-relaxed">{description}</p>
      )}
      {action && (
        <div className="mt-5">
          <Button variant="primary" onClick={action.onClick}>
            {action.label}
          </Button>
        </div>
      )}
    </div>
  );
}
