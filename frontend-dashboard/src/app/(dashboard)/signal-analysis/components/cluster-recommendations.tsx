'use client';

import { CheckSquare, Square, Calendar, ArrowRight, Clock, Target } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';
import {
  CLUSTER_COLORS,
  CLUSTER_NAMES,
  CLUSTER_RECOMMENDATIONS,
  CONTENT_CALENDAR,
} from '../data/sample-data';

function getPriorityBadgeVariant(priority: string): 'terracotta' | 'blue' | 'default' {
  if (priority === 'high') return 'terracotta';
  if (priority === 'medium') return 'blue';
  return 'default';
}

function getPriorityOrder(priority: string): number {
  if (priority === 'high') return 0;
  if (priority === 'medium') return 1;
  return 2;
}

function getGapScoreBadgeClasses(score: number): string {
  if (score >= 0.85) return 'bg-red-50 text-red-700 border-red-200';
  if (score >= 0.7) return 'bg-orange-50 text-orange-700 border-orange-200';
  if (score >= 0.5) return 'bg-amber-50 text-amber-700 border-amber-200';
  return 'bg-green-50 text-green-700 border-green-200';
}

function ClusterContentRecommendations() {
  const sorted = [...CLUSTER_RECOMMENDATIONS].sort(
    (a, b) => getPriorityOrder(a.priority) - getPriorityOrder(b.priority)
  );

  return (
    <div>
      <div className="mb-4">
        <h3 className="font-serif text-base font-semibold text-[#141413]">
          Cluster Content Recommendations
        </h3>
        <p className="text-sm text-stone-500 font-sans mt-0.5">
          Strategic actions per topic cluster, prioritized by opportunity size
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {sorted.map((rec) => {
          const clusterColor = CLUSTER_COLORS[rec.cluster_id] || '#999';

          return (
            <div
              key={rec.cluster_id}
              className="rounded-lg border border-stone-200 bg-white overflow-hidden"
              style={{ borderLeftWidth: 3, borderLeftColor: clusterColor }}
            >
              <div className="p-4">
                {/* Header */}
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: clusterColor }}
                    />
                    <h4 className="font-serif text-sm font-semibold text-[#141413] truncate">
                      {rec.cluster_name}
                    </h4>
                  </div>
                  <Badge
                    variant={getPriorityBadgeVariant(rec.priority)}
                    className="text-[10px] px-1.5 py-0 shrink-0 ml-2"
                  >
                    {rec.priority}
                  </Badge>
                </div>

                {/* Recommendation */}
                <p className="text-xs text-stone-600 font-sans leading-relaxed mb-3">
                  {rec.recommendation}
                </p>

                {/* Key Actions */}
                <div className="space-y-1.5">
                  {rec.key_actions.map((action, i) => (
                    <label
                      key={i}
                      className="flex items-start gap-2 cursor-default group"
                    >
                      <Square className="h-3.5 w-3.5 mt-0.5 shrink-0 text-stone-300 group-hover:text-stone-400 transition-colors" />
                      <span className="text-[11px] text-stone-500 font-sans leading-snug">
                        {action}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ContentCalendarSuggestion() {
  return (
    <div>
      <div className="mb-4">
        <h3 className="font-serif text-base font-semibold text-[#141413]">
          Content Calendar Suggestion
        </h3>
        <p className="text-sm text-stone-500 font-sans mt-0.5">
          Recommended publishing schedule based on gap analysis
        </p>
      </div>

      {/* Timeline container */}
      <div className="relative">
        {/* Horizontal connecting line — visible on md+ */}
        <div className="hidden md:block absolute top-6 left-[5%] right-[5%] h-px bg-gradient-to-r from-stone-200 via-stone-300 to-stone-200 z-0" />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {CONTENT_CALENDAR.map((week, weekIndex) => (
            <div key={week.week} className="relative">
              {/* Timeline dot */}
              <div className="flex items-center gap-2 mb-3 relative z-10">
                <div className="flex h-3 w-3 items-center justify-center rounded-full bg-[#d97757] ring-2 ring-white shadow-sm" />
                <div>
                  <p className="text-xs font-semibold text-[#141413] font-sans">{week.week}</p>
                  <p className="text-[10px] text-stone-400 font-sans">{week.start}</p>
                </div>
                {weekIndex < CONTENT_CALENDAR.length - 1 && (
                  <ArrowRight className="hidden lg:block absolute -right-2 top-0.5 h-3 w-3 text-stone-300" />
                )}
              </div>

              {/* Briefs for this week */}
              <div className="space-y-2 pl-5">
                {week.briefs.map((brief, briefIndex) => {
                  const clusterColor = CLUSTER_COLORS[brief.cluster] || '#999';
                  const clusterName = CLUSTER_NAMES[brief.cluster] || brief.cluster;

                  return (
                    <div
                      key={`${week.week}-${briefIndex}`}
                      className="rounded-md border border-stone-150 bg-stone-50/50 p-2.5 hover:bg-stone-50 transition-colors"
                    >
                      <p className="text-xs text-[#141413] font-sans leading-snug mb-1.5 line-clamp-2">
                        {brief.query_text}
                      </p>
                      <div className="flex items-center justify-between gap-1.5">
                        <Badge
                          variant="default"
                          className="text-[9px] px-1 py-0 text-white"
                          style={{ backgroundColor: clusterColor }}
                        >
                          {clusterName}
                        </Badge>
                        <span
                          className={cn(
                            'inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold font-sans tabular-nums border',
                            getGapScoreBadgeClasses(brief.gap_score)
                          )}
                        >
                          {brief.gap_score.toFixed(3)}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function ClusterRecommendations() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-serif text-lg">Content Strategy Roadmap</CardTitle>
        <CardDescription className="font-sans text-sm text-stone-500">
          Cluster-level recommendations and a phased content calendar
        </CardDescription>

        {/* Summary stats */}
        <div className="flex flex-wrap gap-4 mt-2 text-xs font-sans text-stone-500">
          <span className="flex items-center gap-1">
            <Target className="h-3 w-3" />
            <span className="font-semibold text-[#d97757]">
              {CLUSTER_RECOMMENDATIONS.filter((r) => r.priority === 'high').length}
            </span>{' '}
            high priority
          </span>
          <span className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            <span className="font-semibold text-[#141413]">{CONTENT_CALENDAR.length}</span> weeks planned
          </span>
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            <span className="font-semibold text-[#141413]">
              {CONTENT_CALENDAR.reduce((s, w) => s + w.briefs.length, 0)}
            </span>{' '}
            briefs scheduled
          </span>
        </div>
      </CardHeader>

      <CardContent className="space-y-8">
        <ClusterContentRecommendations />
        <div className="border-t border-stone-100" />
        <ContentCalendarSuggestion />
      </CardContent>
    </Card>
  );
}
