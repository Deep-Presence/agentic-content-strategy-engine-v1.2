'use client';

import { Select } from '@/components/ui/select';
import { useAppStore } from '@/stores/app-store';
import { cn } from '@/lib/utils/cn';

interface CompanySelectorProps {
  className?: string;
}

function CompanySelector({ className }: CompanySelectorProps) {
  const { currentCompany, setCurrentCompany, companies } = useAppStore();

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <Select
        value={currentCompany}
        onChange={(e) => setCurrentCompany(e.target.value)}
        label="Company"
      >
        {companies.length === 0 ? (
          <option value="">No companies</option>
        ) : (
          companies.map((slug) => (
            <option key={slug} value={slug}>
              {slug.charAt(0).toUpperCase() + slug.slice(1)}
            </option>
          ))
        )}
      </Select>
      <Select value="latest" label="Run">
        <option value="latest">Latest</option>
      </Select>
    </div>
  );
}

export { CompanySelector };
export type { CompanySelectorProps };
