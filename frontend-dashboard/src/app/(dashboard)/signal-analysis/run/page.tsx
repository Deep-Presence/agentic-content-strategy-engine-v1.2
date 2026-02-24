import { PageHeader } from '@/components/layout/page-header';
import { PipelineTriggerForm } from '../components/pipeline-trigger-form';

export default function RunNewAnalysisPage() {
  return (
    <div>
      <PageHeader
        title="Run New Analysis"
        description="Start a new Deep Signal Analysis pipeline to analyze AI citation patterns."
      />
      <div className="mt-6 max-w-2xl">
        <PipelineTriggerForm />
      </div>
    </div>
  );
}
