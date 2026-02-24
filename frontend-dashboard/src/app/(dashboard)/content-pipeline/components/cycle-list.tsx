import { cn } from '@/lib/utils/cn';
import { CycleCard } from './cycle-card';
import type { Cycle } from '@/types/content';

interface CycleListProps {
  activeCycle: Cycle | null;
  pastCycles: Cycle[];
  className?: string;
}

export function CycleList({ activeCycle, pastCycles, className }: CycleListProps) {
  return (
    <div className={cn('space-y-8', className)}>
      {activeCycle && (
        <div className="space-y-3">
          <h2 className="font-serif text-heading-3 text-cream-950">Active Cycle</h2>
          <CycleCard cycle={activeCycle} isActive />
        </div>
      )}

      {pastCycles.length > 0 && (
        <div className="space-y-3">
          <h2 className="font-serif text-heading-3 text-cream-950">Past Cycles</h2>
          <div className="space-y-3">
            {pastCycles.map((cycle) => (
              <CycleCard key={cycle.id} cycle={cycle} />
            ))}
          </div>
        </div>
      )}

      {!activeCycle && pastCycles.length === 0 && (
        <div className="text-center py-12">
          <p className="text-body font-sans text-cream-600">No cycles created yet.</p>
          <p className="text-body-sm font-sans text-cream-500 mt-1">
            Cycles group content briefs into weekly sprints.
          </p>
        </div>
      )}
    </div>
  );
}
