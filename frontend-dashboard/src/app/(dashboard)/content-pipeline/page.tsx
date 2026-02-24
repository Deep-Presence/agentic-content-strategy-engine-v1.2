import { FileText } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';

export default function ContentPipelinePage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Content Pipeline"
        description="Linear-style content management with cycles and roadmaps"
      />
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <FileText className="h-12 w-12 text-cream-500 mb-4" />
        <h2 className="font-serif text-heading-3 text-cream-800 mb-2">Coming Soon</h2>
        <p className="text-body text-cream-600 max-w-md">
          The Content Pipeline will include brief management, a rich text editor,
          cycle tracking, and content analytics.
        </p>
      </div>
    </div>
  );
}
