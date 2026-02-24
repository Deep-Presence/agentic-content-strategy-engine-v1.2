import { Brain } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';

export default function BrandBrainPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Brand Brain"
        description="Knowledge bases, projects, personas, and research triggers"
      />
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <Brain className="h-12 w-12 text-cream-500 mb-4" />
        <h2 className="font-serif text-heading-3 text-cream-800 mb-2">Coming Soon</h2>
        <p className="text-body text-cream-600 max-w-md">
          Brand Brain will manage your company profiles, personas, style guides,
          and knowledge documents.
        </p>
      </div>
    </div>
  );
}
