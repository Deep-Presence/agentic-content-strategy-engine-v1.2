'use client';

import { useState } from 'react';
import {
  Play,
  Clock,
  Search,
  FileText,
  BarChart3,
  TrendingUp,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';
import { RUN_HISTORY, SPA_SCORE_TREND, type RunHistoryItem } from '../data/sample-data';
import { GAP_ANALYSIS_STEPS } from '@/types/gap-analysis';
import { PipelineVisualizerHorizontal } from './pipeline-visualizer-horizontal';

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function getStatusBadgeVariant(
  status: RunHistoryItem['status']
): 'success' | 'blue' | 'error' {
  switch (status) {
    case 'completed':
      return 'success';
    case 'running':
      return 'blue';
    case 'failed':
      return 'error';
  }
}

function getStatusLabel(status: RunHistoryItem['status']): string {
  switch (status) {
    case 'completed':
      return 'Completed';
    case 'running':
      return 'Running';
    case 'failed':
      return 'Failed';
  }
}

function buildPipelineSteps(run: RunHistoryItem) {
  return GAP_ANALYSIS_STEPS.map((step, index) => {
    let status: 'completed' | 'active' | 'waiting';
    if (index < run.steps_completed) {
      status = 'completed';
    } else if (index === run.steps_completed) {
      status = run.status === 'running' ? 'active' : 'waiting';
    } else {
      status = 'waiting';
    }

    return {
      key: step.key,
      label: step.label,
      description: step.description,
      status,
      duration: status === 'completed' ? undefined : undefined,
    };
  });
}

export function RunHistoryTable() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const selectedRun = RUN_HISTORY.find((r) => r.id === selectedRunId) ?? null;

  return (
    <div className="space-y-6">
      {/* Section A: Analysis Runs Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="font-serif text-lg">Analysis Runs</CardTitle>
              <CardDescription className="font-sans text-sm text-gray-500">
                History of gap analysis pipeline executions
              </CardDescription>
            </div>
            <Button variant="primary" size="sm">
              <Play className="w-4 h-4 mr-1.5" />
              Run New Analysis
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm font-sans">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50/60">
                  <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">
                    Run ID
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">
                    Company
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">
                    Status
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">
                    Started
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">
                    Duration
                  </th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">
                    <Search className="w-3.5 h-3.5 inline mr-1" />
                    Queries
                  </th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">
                    <FileText className="w-3.5 h-3.5 inline mr-1" />
                    Citations
                  </th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">
                    <BarChart3 className="w-3.5 h-3.5 inline mr-1" />
                    SPA Score
                  </th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">
                    Steps
                  </th>
                </tr>
              </thead>
              <tbody>
                {RUN_HISTORY.map((run) => {
                  const isSelected = selectedRunId === run.id;
                  return (
                    <tr
                      key={run.id}
                      onClick={() =>
                        setSelectedRunId(isSelected ? null : run.id)
                      }
                      className={cn(
                        'border-b border-gray-100 cursor-pointer transition-colors',
                        isSelected
                          ? 'bg-[#d97757]/5 border-l-2 border-l-[#d97757]'
                          : 'hover:bg-gray-50/80'
                      )}
                    >
                      <td className="px-4 py-3 font-mono text-xs text-gray-600">
                        {run.id.slice(0, 8)}...
                      </td>
                      <td className="px-4 py-3 font-medium text-[#141413]">
                        {run.company}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={getStatusBadgeVariant(run.status)}>
                          {getStatusLabel(run.status)}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {formatDate(run.started)}
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        <Clock className="w-3.5 h-3.5 inline mr-1 text-gray-400" />
                        {run.duration}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-gray-700">
                        {run.queries}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-gray-700">
                        {run.citations}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span
                          className={cn(
                            'font-semibold tabular-nums',
                            run.spa_score >= 40
                              ? 'text-[#788c5d]'
                              : run.spa_score >= 25
                                ? 'text-[#d97757]'
                                : 'text-red-500'
                          )}
                        >
                          {run.spa_score.toFixed(1)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-xs text-gray-600">
                        {run.steps_completed}/8
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Section B: Pipeline Steps Visualizer (shown when a run is selected) */}
      {selectedRun && (
        <Card>
          <CardHeader>
            <CardTitle className="font-serif text-lg">
              Pipeline Steps
              <span className="ml-2 font-sans text-sm font-normal text-gray-500">
                {selectedRun.company} — {selectedRun.id.slice(0, 8)}
              </span>
            </CardTitle>
            <CardDescription className="font-sans text-sm text-gray-500">
              8-step gap analysis pipeline progress
              {selectedRun.status === 'completed' && (
                <span className="ml-2 text-[#788c5d]">
                  — Total duration: {selectedRun.duration}
                </span>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <PipelineVisualizerHorizontal
              steps={buildPipelineSteps(selectedRun)}
            />
          </CardContent>
        </Card>
      )}

      {/* Section C: SPA Score Trend Chart */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-[#6a9bcc]" />
            <div>
              <CardTitle className="font-serif text-lg">SPA Score Trend</CardTitle>
              <CardDescription className="font-sans text-sm text-gray-500">
                Score improvement across analysis runs
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-[280px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={SPA_SCORE_TREND}
                margin={{ top: 8, right: 24, left: 0, bottom: 8 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#e5e5e5"
                  vertical={false}
                />
                <XAxis
                  dataKey="run"
                  tick={{ fontSize: 12, fill: '#6b7280', fontFamily: 'sans-serif' }}
                  axisLine={{ stroke: '#d1d5db' }}
                  tickLine={false}
                />
                <YAxis
                  domain={[10, 'auto']}
                  tick={{ fontSize: 12, fill: '#6b7280', fontFamily: 'sans-serif' }}
                  axisLine={{ stroke: '#d1d5db' }}
                  tickLine={false}
                  width={40}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#faf9f5',
                    border: '1px solid #e5e5e5',
                    borderRadius: '8px',
                    fontSize: '13px',
                    fontFamily: 'sans-serif',
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)',
                  }}
                  labelStyle={{ color: '#141413', fontWeight: 600 }}
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  formatter={((value: any) => [
                    `${typeof value === 'number' ? value.toFixed(1) : value}`,
                    'SPA Score',
                  ]) as any}
                />
                <Line
                  type="monotone"
                  dataKey="spa_score"
                  stroke="#6a9bcc"
                  strokeWidth={2.5}
                  dot={{
                    fill: '#6a9bcc',
                    stroke: '#fff',
                    strokeWidth: 2,
                    r: 5,
                  }}
                  activeDot={{
                    fill: '#6a9bcc',
                    stroke: '#fff',
                    strokeWidth: 2,
                    r: 7,
                  }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
