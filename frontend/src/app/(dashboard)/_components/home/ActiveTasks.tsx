'use client';

import { Card, Badge, ProgressBar } from '@/components/ui';
import { useRouter } from 'next/navigation';
import { Zap } from 'lucide-react';

interface Task {
  id: string;
  title: string;
  stage: string;
  agent: string;
  progress: number;
}

const DEMO_TASKS: Task[] = [
  {
    id: 'brief-001',
    title: 'International Equity Grants: Compliance Risks & Mitigation',
    stage: 'Enriching content',
    agent: 'Content Agent',
    progress: 72,
  },
  {
    id: 'brief-002',
    title: 'No-Code vs Low-Code: Technical Decision Framework',
    stage: 'Generating draft',
    agent: 'Content Agent',
    progress: 45,
  },
  {
    id: 'brief-003',
    title: 'AI-Powered App Building for Non-Technical Founders',
    stage: 'Outline complete',
    agent: 'Research Agent',
    progress: 28,
  },
];

export function ActiveTasks() {
  const router = useRouter();

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Zap size={16} strokeWidth={1.5} className="text-accent" />
        <h2 className="text-[18px] font-semibold text-text-primary">Active Agent Tasks</h2>
      </div>
      <div className="space-y-2">
        {DEMO_TASKS.map((task) => (
          <Card
            key={task.id}
            hoverable
            className="cursor-pointer"
            onClick={() => router.push('/content')}
          >
            <div className="flex items-center justify-between mb-2">
              <p className="text-[14px] font-medium text-text-primary leading-[1.4]">{task.title}</p>
            </div>
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="info">{task.stage}</Badge>
              <span className="text-[12px] text-text-tertiary">{task.agent}</span>
            </div>
            <ProgressBar value={task.progress} />
            <p className="text-[12px] text-text-tertiary mt-1.5">{task.progress}% complete</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
