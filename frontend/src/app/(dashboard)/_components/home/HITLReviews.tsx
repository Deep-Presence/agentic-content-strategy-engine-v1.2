'use client';

import { Card, Badge } from '@/components/ui';
import { useRouter } from 'next/navigation';
import { AlertCircle, FileText, PenTool } from 'lucide-react';

interface ReviewItem {
  id: string;
  title: string;
  type: 'brief' | 'article';
  priority: 'high' | 'medium';
}

const DEMO_REVIEWS: ReviewItem[] = [
  { id: '1', title: 'International Equity Grants — brief outline', type: 'brief', priority: 'high' },
  { id: '2', title: 'No-Code vs Low-Code — draft review', type: 'article', priority: 'high' },
  { id: '3', title: 'AI App Building — persona alignment check', type: 'brief', priority: 'medium' },
  { id: '4', title: 'Remote Team Equity — voice compliance review', type: 'article', priority: 'medium' },
];

export function HITLReviews() {
  const router = useRouter();
  const briefCount = DEMO_REVIEWS.filter((r) => r.type === 'brief').length;
  const articleCount = DEMO_REVIEWS.filter((r) => r.type === 'article').length;

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <AlertCircle size={16} strokeWidth={1.5} className="text-warning" />
        <h2 className="text-[18px] font-semibold text-text-primary">HITL Reviews Pending</h2>
      </div>

      {/* Summary badges */}
      <div className="flex gap-2 mb-3">
        <Badge variant="warning">{briefCount} briefs</Badge>
        <Badge variant="warning">{articleCount} articles</Badge>
      </div>

      <div className="space-y-2">
        {DEMO_REVIEWS.map((item) => (
          <Card
            key={item.id}
            hoverable
            className="cursor-pointer"
            onClick={() => router.push('/content')}
          >
            <div className="flex items-center gap-3">
              <div className="flex-shrink-0 text-text-tertiary">
                {item.type === 'brief' ? (
                  <FileText size={16} strokeWidth={1.5} />
                ) : (
                  <PenTool size={16} strokeWidth={1.5} />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[14px] text-text-primary leading-[1.4]">{item.title}</p>
              </div>
              <Badge variant={item.priority === 'high' ? 'error' : 'warning'}>
                {item.priority}
              </Badge>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
