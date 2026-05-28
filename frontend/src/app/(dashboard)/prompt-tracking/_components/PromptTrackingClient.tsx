'use client';

import { cn } from '@/lib/utils';
import { useState, useMemo, useEffect } from 'react';
import {
  Search,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronDown,
  ChevronRight,
  Play,
  Loader2,
} from 'lucide-react';
import { Sparkline, SlideDrawer, DateRangePicker } from '@/components/ui';
import type { DateRange } from '@/components/ui/DateRangePicker';
import { subDays, format } from 'date-fns';
import { usePromptTrackingData } from '../_hooks/usePromptTrackingData';
import { triggerDailyRun, fetchRunStatus } from '../_lib/api';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/hooks/useAuth';
import { useRef, useCallback } from 'react';
import type { PromptRow, Topic } from '../_lib/types';
import { PromptTableSkeleton } from './PromptTrackingSkeleton';
import { PromptDetailDrawer } from './PromptDetailDrawer';
import { AddPromptModal } from './AddPromptModal';

// === Helpers ===

function DeltaValue({ value }: { value: number }) {
  if (value === 0) return <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', marginLeft: 4 }}>0.0%</span>;
  const pos = value > 0;
  return (
    <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, color: pos ? 'var(--success)' : 'var(--error)', marginLeft: 4 }}>
      {pos ? '+' : ''}{(value * 100).toFixed(1)}%
    </span>
  );
}

/** Live elapsed-time counter. */
function ElapsedTimer({ startedAt }: { startedAt: number }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => clearInterval(t);
  }, [startedAt]);
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  return (
    <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', marginLeft: 'auto' }}>
      {mins > 0 ? `${mins}m ${secs}s` : `${secs}s`}
    </span>
  );
}

type SortKey = 'text' | 'topic' | 'queryFanouts' | 'mentionRate' | 'citationRate';
type SortDir = 'asc' | 'desc';

// === Toast ===

function ActionToast({ visible, message }: { visible: boolean; message: string }) {
  return (
    <div
      className={cn(
        'fixed bottom-6 right-6 z-[60] transition-all duration-200',
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2 pointer-events-none'
      )}
      style={{
        padding: '8px 14px',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border)',
        background: 'var(--surface-raised)',
        boxShadow: 'var(--shadow-float)',
        fontSize: 13,
        color: 'var(--text-primary)',
      }}
    >
      {message}
    </div>
  );
}

// === Main Component ===

export function PromptTrackingClient() {
  const [view, setView] = useState<'prompt' | 'topic'>('prompt');
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('mentionRate');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [topicFilter, setTopicFilter] = useState('all');
  const [selectedPrompt, setSelectedPrompt] = useState<PromptRow | null>(null);
  const [toastVisible, setToastVisible] = useState(false);
  const [toastMessage, setToastMessage] = useState('Coming soon');
  const [addModalOpen, setAddModalOpen] = useState(false);
  // Track active fanout generation tasks: promptId → taskId
  const [fanoutTasks, setFanoutTasks] = useState<Record<string, string>>({});
  const [pipelineStatus, setPipelineStatus] = useState<
    | { state: 'idle' }
    | { state: 'starting' }
    | { state: 'running'; runId: string; startedAt: number; promptCount: number; engineCount: number }
    | { state: 'completed'; promptCount: number; engineCount: number }
    | { state: 'failed'; error: string }
  >(() => {
    // Recover active run from localStorage on mount
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('dp:activeRunId');
      if (saved) {
        try {
          const { runId, startedAt } = JSON.parse(saved);
          return { state: 'running' as const, runId, startedAt, promptCount: 0, engineCount: 0 };
        } catch { /* ignore corrupt data */ }
      }
    }
    return { state: 'idle' as const };
  });
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [autoRunEnabled, setAutoRunEnabled] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('dp:autoRunDaily') === 'true';
    }
    return false;
  });
  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(new Set());

  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: subDays(new Date(), 6),
    to: new Date(),
  });

  // Debounced search: 300ms delay
  const [debouncedSearch, setDebouncedSearch] = useState('');
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const dateParams = useMemo(() => {
    if (dateRange?.from && dateRange?.to) {
      return {
        start_date: format(dateRange.from, 'yyyy-MM-dd'),
        end_date: format(dateRange.to, 'yyyy-MM-dd'),
      };
    }
    return { days: 7 };
  }, [dateRange]);

  const { prompts, topics, total, periodStart, periodEnd, isLoading, error, refetch } = usePromptTrackingData(
    dateParams,
    topicFilter === 'all' ? undefined : topicFilter,
    debouncedSearch || undefined,
  );

  const { companyName } = useAuth();

  /** Start polling a run until it completes or fails. */
  const startPolling = useCallback((runId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const status = await fetchRunStatus(runId);
        if (status.status === 'completed') {
          if (pollRef.current) clearInterval(pollRef.current);
          localStorage.removeItem('dp:activeRunId');
          setPipelineStatus({
            state: 'completed',
            promptCount: status.prompt_count,
            engineCount: status.engine_count,
          });
          refetch();
          setTimeout(() => setPipelineStatus({ state: 'idle' }), 6000);
        } else if (status.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current);
          localStorage.removeItem('dp:activeRunId');
          setPipelineStatus({ state: 'failed', error: status.error || 'Run failed' });
          setTimeout(() => setPipelineStatus({ state: 'idle' }), 8000);
        } else {
          setPipelineStatus((prev) =>
            prev.state === 'running'
              ? { ...prev, promptCount: status.prompt_count, engineCount: status.engine_count }
              : prev,
          );
        }
      } catch {
        // Polling error — keep trying
      }
    }, 5000);
  }, [refetch]);

  // On mount: if we recovered an active run from localStorage, resume polling
  useEffect(() => {
    if (pipelineStatus.state === 'running' && pipelineStatus.runId) {
      // Check immediately, then poll
      fetchRunStatus(pipelineStatus.runId).then((status) => {
        if (status.status === 'completed') {
          localStorage.removeItem('dp:activeRunId');
          setPipelineStatus({
            state: 'completed',
            promptCount: status.prompt_count,
            engineCount: status.engine_count,
          });
          refetch();
          setTimeout(() => setPipelineStatus({ state: 'idle' }), 6000);
        } else if (status.status === 'failed') {
          localStorage.removeItem('dp:activeRunId');
          setPipelineStatus({ state: 'failed', error: status.error || 'Run failed' });
          setTimeout(() => setPipelineStatus({ state: 'idle' }), 8000);
        } else {
          startPolling(pipelineStatus.runId);
        }
      }).catch(() => {
        // If status fetch fails, still start polling
        startPolling(pipelineStatus.runId);
      });
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRunAll = async () => {
    if (pipelineStatus.state === 'starting' || pipelineStatus.state === 'running' || prompts.length === 0) return;
    setPipelineStatus({ state: 'starting' });
    try {
      const result = await triggerDailyRun({
        brand: companyName || undefined,
      });
      const startedAt = Date.now();
      localStorage.setItem('dp:activeRunId', JSON.stringify({ runId: result.run_id, startedAt }));
      setPipelineStatus({
        state: 'running',
        runId: result.run_id,
        startedAt,
        promptCount: 0,
        engineCount: 0,
      });
      startPolling(result.run_id);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to start run';
      setPipelineStatus({ state: 'failed', error: msg });
      setTimeout(() => setPipelineStatus({ state: 'idle' }), 5000);
    }
  };

  const handleAutoRunToggle = (checked: boolean) => {
    setAutoRunEnabled(checked);
    localStorage.setItem('dp:autoRunDaily', String(checked));
  };

  // Auto-expand all topics when data loads
  useEffect(() => {
    if (topics.length > 0) {
      setExpandedTopics(new Set(topics.map((t) => t.name)));
    }
  }, [topics]);

  const showToast = (msg = 'Coming soon') => {
    setToastMessage(msg);
    setToastVisible(true);
    setTimeout(() => setToastVisible(false), 2000);
  };

  // Client-side sorting only (search and topic filtering are server-side)
  const sortedPrompts = useMemo(() => {
    const list = [...prompts];
    list.sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDir === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });
    return list;
  }, [prompts, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('desc'); }
  };

  const SortIcon = ({ column }: { column: SortKey }) => {
    if (sortKey !== column) return <ArrowUpDown size={11} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />;
    return sortDir === 'asc'
      ? <ArrowUp size={11} strokeWidth={1.5} style={{ color: 'var(--accent)' }} />
      : <ArrowDown size={11} strokeWidth={1.5} style={{ color: 'var(--accent)' }} />;
  };

  const toggleTopicExpand = (topic: string) => {
    setExpandedTopics((prev) => {
      const next = new Set(prev);
      if (next.has(topic)) next.delete(topic);
      else next.add(topic);
      return next;
    });
  };

  const clearFilters = () => { setTopicFilter('all'); setSearch(''); };
  const hasFilters = topicFilter !== 'all' || search.length > 0;

  // Shared column header style
  const thStyle: React.CSSProperties = {
    fontSize: 11,
    fontWeight: 500,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    color: 'var(--text-secondary)',
    textAlign: 'left',
    padding: '6px 8px',
    borderBottom: '1px solid var(--border)',
    whiteSpace: 'nowrap',
  };

  return (
    <div>
      {/* Page title: 22px, directly above filter bar (0 gap) */}
      <div style={{ padding: '0 0 8px' }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>Prompt Tracking</h1>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '2px 0 0' }}>
          What are people asking AI engines, and are you showing up in the answers?
        </p>
      </div>

      {/* Global Filter Bar: full-width, border-bottom only, 44px, no rounded corners, no background */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        height: 44,
        padding: '0 4px',
        borderBottom: '1px solid var(--border)',
      }}>
        {/* Date range */}
        <DateRangePicker value={dateRange} onChange={setDateRange} />

        {/* Divider */}
        <div style={{ width: 1, height: 16, background: 'var(--border)' }} />

        {/* Topic filter */}
        <select
          value={topicFilter}
          onChange={(e) => setTopicFilter(e.target.value)}
          style={{
            height: 28,
            padding: '0 8px',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            background: 'transparent',
            fontSize: 13,
            color: 'var(--text-primary)',
            outline: 'none',
            cursor: 'pointer',
          }}
        >
          <option value="all">All Topics</option>
          {topics.map((t) => <option key={t.name} value={t.name}>{t.name}</option>)}
        </select>

        {/* Clear */}
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="cursor-pointer"
            style={{
              fontSize: 12,
              color: 'var(--text-secondary)',
              background: 'none',
              border: 'none',
              padding: 0,
            }}
          >
            × Clear
          </button>
        )}

        {/* Right-aligned: auto-run toggle + run button */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Auto-run checkbox */}
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            <input
              type="checkbox"
              checked={autoRunEnabled}
              onChange={(e) => handleAutoRunToggle(e.target.checked)}
              style={{ width: 13, height: 13, accentColor: 'var(--accent)' }}
            />
            Auto-run daily
          </label>

          {/* Divider */}
          <div style={{ width: 1, height: 16, background: 'var(--border)' }} />

          {/* Run All button */}
          <button
            onClick={handleRunAll}
            disabled={pipelineStatus.state === 'starting' || pipelineStatus.state === 'running' || prompts.length === 0}
            className="cursor-pointer"
            style={{
              height: 28,
              padding: '0 12px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--accent)',
              background: pipelineStatus.state === 'running' || pipelineStatus.state === 'starting' ? 'var(--accent-subtle)' : 'transparent',
              color: 'var(--accent)',
              fontSize: 12,
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              opacity: prompts.length === 0 ? 0.5 : 1,
              whiteSpace: 'nowrap',
            }}
          >
            {pipelineStatus.state === 'starting' || pipelineStatus.state === 'running' ? (
              <Loader2 size={12} strokeWidth={2} className="animate-spin" />
            ) : (
              <Play size={11} strokeWidth={2} />
            )}
            {pipelineStatus.state === 'starting' ? 'Starting...' : pipelineStatus.state === 'running' ? 'Running...' : 'Run All Prompts'}
          </button>
        </div>
      </div>

      {/* Sub-nav bar: tabs left, search+actions right, 44px, border-bottom */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        height: 44,
        padding: '0 4px',
        borderBottom: '1px solid var(--border)',
      }}>
        {/* Prompt / Topic tabs */}
        <div style={{ display: 'flex', gap: 16 }}>
          {(['prompt', 'topic'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setView(tab)}
              className="cursor-pointer"
              style={{
                fontSize: 13,
                fontWeight: view === tab ? 600 : 400,
                color: view === tab ? 'var(--text-primary)' : 'var(--text-secondary)',
                background: 'none',
                border: 'none',
                borderBottom: view === tab ? '2px solid var(--accent)' : '2px solid transparent',
                padding: '0 0 8px',
                marginBottom: -1,
              }}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Right: search + actions */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Search */}
          <div style={{ position: 'relative' }}>
            <Search size={13} strokeWidth={1.5} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-tertiary)' }} />
            <input
              type="text"
              placeholder="Search prompts..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: 200,
                height: 28,
                paddingLeft: 28,
                paddingRight: 10,
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                background: 'transparent',
                fontSize: 12,
                color: 'var(--text-primary)',
                outline: 'none',
              }}
            />
          </div>

          <button
            onClick={() => showToast()}
            className="cursor-pointer"
            style={{
              fontSize: 12,
              color: 'var(--text-secondary)',
              background: 'none',
              border: 'none',
              padding: 0,
            }}
          >
            ✏️ Edit Topics
          </button>

          <button
            onClick={() => setAddModalOpen(true)}
            className="cursor-pointer"
            style={{
              height: 28,
              padding: '0 10px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--accent)',
              color: 'white',
              fontSize: 12,
              fontWeight: 500,
              border: 'none',
            }}
          >
            + Add Prompts
          </button>
        </div>
      </div>

      {/* Pipeline run status banner */}
      {pipelineStatus.state !== 'idle' && (
        <div
          style={{
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '10px 12px',
            borderBottom: '1px solid var(--border)',
            background: pipelineStatus.state === 'failed'
              ? 'rgba(229, 72, 77, 0.06)'
              : pipelineStatus.state === 'completed'
                ? 'rgba(52, 178, 123, 0.06)'
                : 'var(--accent-subtle)',
            fontSize: 13,
            transition: 'all 0.3s ease',
          }}
        >
          {/* Icon / spinner */}
          {(pipelineStatus.state === 'starting' || pipelineStatus.state === 'running') && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Loader2 size={15} strokeWidth={2} className="animate-spin" style={{ color: 'var(--accent)' }} />
              <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                {pipelineStatus.state === 'starting'
                  ? 'Starting pipeline...'
                  : 'Running prompts across AI engines'}
              </span>
              {pipelineStatus.state === 'running' && (
                <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                  {pipelineStatus.promptCount > 0
                    ? `${pipelineStatus.promptCount} prompts × ${pipelineStatus.engineCount} engines`
                    : 'Initializing...'}
                </span>
              )}
              {/* Elapsed time */}
              {pipelineStatus.state === 'running' && <ElapsedTimer startedAt={pipelineStatus.startedAt} />}
            </div>
          )}
          {pipelineStatus.state === 'completed' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 15 }}>&#10003;</span>
              <span style={{ color: 'var(--success)', fontWeight: 500 }}>
                Run complete — {pipelineStatus.promptCount} prompts checked across {pipelineStatus.engineCount} engines
              </span>
            </div>
          )}
          {pipelineStatus.state === 'failed' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 15, color: 'var(--error)' }}>&#10007;</span>
              <span style={{ color: 'var(--error)', fontWeight: 500 }}>
                Run failed: {pipelineStatus.error}
              </span>
            </div>
          )}

          {/* Dismiss button */}
          {(pipelineStatus.state === 'completed' || pipelineStatus.state === 'failed') && (
            <button
              onClick={() => { localStorage.removeItem('dp:activeRunId'); setPipelineStatus({ state: 'idle' }); }}
              className="cursor-pointer"
              style={{
                marginLeft: 'auto',
                fontSize: 11,
                color: 'var(--text-secondary)',
                background: 'none',
                border: 'none',
                padding: 0,
              }}
            >
              Dismiss
            </button>
          )}

          {/* Animated indeterminate progress bar */}
          {(pipelineStatus.state === 'starting' || pipelineStatus.state === 'running') && (
            <div
              style={{
                position: 'absolute',
                left: 0,
                bottom: 0,
                height: 2,
                width: '100%',
                background: 'var(--border)',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: '35%',
                  background: 'var(--accent)',
                  borderRadius: 1,
                  animation: 'indeterminate 1.6s ease-in-out infinite',
                }}
              />
              <style>{`
                @keyframes indeterminate {
                  0% { transform: translateX(-100%); }
                  100% { transform: translateX(380%); }
                }
              `}</style>
            </div>
          )}
        </div>
      )}

      {/* Loading state */}
      {isLoading && prompts.length === 0 && <PromptTableSkeleton />}

      {/* Error state */}
      {error && prompts.length === 0 && (
        <div style={{ padding: 40, textAlign: 'center' }}>
          <p style={{ fontSize: 14, color: 'var(--error)', marginBottom: 12 }}>{error}</p>
          <button onClick={refetch} style={{ fontSize: 13, color: 'var(--accent)', background: 'none', border: '1px solid var(--accent)', borderRadius: 'var(--radius-sm)', padding: '6px 16px', cursor: 'pointer' }}>
            Retry
          </button>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && prompts.length === 0 && (
        <div style={{ padding: 60, textAlign: 'center' }}>
          <p style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>No prompts tracked yet</p>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Add your first prompt to start monitoring AI visibility.</p>
        </div>
      )}

      {/* Table */}
      {prompts.length > 0 && (
        <div style={{ border: '1px solid var(--border)', borderTop: 'none' }}>
          {view === 'prompt' ? (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th onClick={() => handleSort('text')} className="cursor-pointer" style={{ ...thStyle, width: '35%' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>Prompt <SortIcon column="text" /></span>
                  </th>
                  <th onClick={() => handleSort('topic')} className="cursor-pointer" style={{ ...thStyle, width: '15%' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>Topic <SortIcon column="topic" /></span>
                  </th>
                  <th style={{ ...thStyle, width: '10%' }}>Tags</th>
                  <th onClick={() => handleSort('queryFanouts')} className="cursor-pointer" style={{ ...thStyle, width: '8%' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>Fanouts <SortIcon column="queryFanouts" /></span>
                  </th>
                  <th style={{ ...thStyle, width: '10%' }}>Volume</th>
                  <th onClick={() => handleSort('mentionRate')} className="cursor-pointer" style={{ ...thStyle, width: '11%' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>Mention Rate <SortIcon column="mentionRate" /></span>
                  </th>
                  <th onClick={() => handleSort('citationRate')} className="cursor-pointer" style={{ ...thStyle, width: '11%' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>Citation Rate <SortIcon column="citationRate" /></span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedPrompts.map((p) => (
                  <PromptTableRow key={p.id} prompt={p} onClick={() => setSelectedPrompt(p)} />
                ))}
              </tbody>
            </table>
          ) : (
            <TopicGroupedView
              prompts={sortedPrompts}
              topics={topics}
              handleSort={handleSort}
              SortIcon={SortIcon}
              thStyle={thStyle}
              expandedTopics={expandedTopics}
              toggleTopicExpand={toggleTopicExpand}
              onRowClick={setSelectedPrompt}
            />
          )}
        </div>
      )}

      {/* Footer: 11px */}
      {prompts.length > 0 && (
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 8 }}>
          {sortedPrompts.length} of {total} prompts
        </div>
      )}

      {/* Drawer */}
      <SlideDrawer open={!!selectedPrompt} onClose={() => setSelectedPrompt(null)}>
        {selectedPrompt && (
          <PromptDetailDrawer
            prompt={selectedPrompt}
            dateParams={dateParams}
            fanoutTaskId={fanoutTasks[selectedPrompt.id] ?? null}
            onFanoutComplete={() => {
              setFanoutTasks((prev) => {
                const next = { ...prev };
                delete next[selectedPrompt.id];
                return next;
              });
            }}
          />
        )}
      </SlideDrawer>

      <AddPromptModal
        open={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        onCreated={(promptId, fanoutTaskId) => {
          if (fanoutTaskId) {
            setFanoutTasks((prev) => ({ ...prev, [promptId]: fanoutTaskId }));
          }
          refetch();
        }}
      />

      <ActionToast visible={toastVisible} message={toastMessage} />
    </div>
  );
}

// === Prompt Table Row ===

function PromptTableRow({ prompt: p, onClick }: { prompt: PromptRow; onClick: () => void }) {
  const cellStyle: React.CSSProperties = {
    padding: '6px 8px',
    borderBottom: '1px solid var(--border-subtle)',
    verticalAlign: 'middle',
  };

  return (
    <tr
      onClick={onClick}
      className="cursor-pointer"
      style={{ height: 40, transition: 'background 0.1s' }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      {/* Prompt: 13px font-weight 500, ellipsis */}
      <td style={cellStyle}>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {p.text}
        </div>
      </td>
      {/* Topic: 11px colored pill, max-width 200px */}
      <td style={cellStyle}>
        <span
          style={{
            display: 'inline-block',
            maxWidth: 200,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            fontSize: 11,
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: 'var(--radius-full)',
            background: `${p.topicColor}18`,
            color: p.topicColor,
          }}
        >
          {p.topic}
        </span>
      </td>
      {/* Tags: 10px pills */}
      <td style={cellStyle}>
        {p.tags.length > 0 ? (
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {p.tags.map((tag) => (
              <span
                key={tag}
                style={{
                  fontSize: 10,
                  padding: '2px 6px',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--text-secondary)',
                }}
              >
                {tag}
              </span>
            ))}
          </div>
        ) : (
          <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>—</span>
        )}
      </td>
      {/* Fanouts: 13px JetBrains Mono */}
      <td style={cellStyle}>
        <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
          ↗ {p.queryFanouts}
        </span>
      </td>
      {/* Volume: 56×14 sparkline, green stroke */}
      <td style={cellStyle}>
        <Sparkline data={p.volume} width={56} height={14} />
      </td>
      {/* Mention Rate: 13px + delta 11px, single line, 4px gap */}
      <td style={cellStyle}>
        <span style={{ whiteSpace: 'nowrap' }}>
          <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
            {(p.mentionRate * 100).toFixed(1)}%
          </span>
          <DeltaValue value={p.mentionDelta} />
        </span>
      </td>
      {/* Citation Rate */}
      <td style={cellStyle}>
        <span style={{ whiteSpace: 'nowrap' }}>
          <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
            {(p.citationRate * 100).toFixed(1)}%
          </span>
          <DeltaValue value={p.citationDelta} />
        </span>
      </td>
    </tr>
  );
}

// === Topic Grouped View ===

function TopicGroupedView({
  prompts,
  topics,
  handleSort,
  SortIcon,
  thStyle,
  expandedTopics,
  toggleTopicExpand,
  onRowClick,
}: {
  prompts: PromptRow[];
  topics: Topic[];
  handleSort: (key: SortKey) => void;
  SortIcon: React.ComponentType<{ column: SortKey }>;
  thStyle: React.CSSProperties;
  expandedTopics: Set<string>;
  toggleTopicExpand: (topic: string) => void;
  onRowClick: (p: PromptRow) => void;
}) {
  const topicGroups = useMemo(() => {
    const groups: Record<string, PromptRow[]> = {};
    for (const p of prompts) {
      if (!groups[p.topic]) groups[p.topic] = [];
      groups[p.topic].push(p);
    }
    return groups;
  }, [prompts]);

  return (
    <div>
      {/* Table header */}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th onClick={() => handleSort('text')} className="cursor-pointer" style={{ ...thStyle, width: '35%' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>Prompt <SortIcon column="text" /></span>
            </th>
            <th onClick={() => handleSort('topic')} className="cursor-pointer" style={{ ...thStyle, width: '15%' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>Topic <SortIcon column="topic" /></span>
            </th>
            <th style={{ ...thStyle, width: '10%' }}>Tags</th>
            <th onClick={() => handleSort('queryFanouts')} className="cursor-pointer" style={{ ...thStyle, width: '8%' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>Fanouts <SortIcon column="queryFanouts" /></span>
            </th>
            <th style={{ ...thStyle, width: '10%' }}>Volume</th>
            <th onClick={() => handleSort('mentionRate')} className="cursor-pointer" style={{ ...thStyle, width: '11%' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>Mention Rate <SortIcon column="mentionRate" /></span>
            </th>
            <th onClick={() => handleSort('citationRate')} className="cursor-pointer" style={{ ...thStyle, width: '11%' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>Citation Rate <SortIcon column="citationRate" /></span>
            </th>
          </tr>
        </thead>
      </table>

      {/* Topic groups with colored left border */}
      {topics.filter((t) => topicGroups[t.name]).map((topic) => {
        const groupPrompts = topicGroups[topic.name];
        const isExpanded = expandedTopics.has(topic.name);

        return (
          <div key={topic.name} style={{ borderLeft: `2px solid ${topic.color}` }}>
            {/* Topic header: 12px, collapsible */}
            <button
              onClick={() => toggleTopicExpand(topic.name)}
              className="cursor-pointer"
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 8px',
                border: 'none',
                borderBottom: '1px solid var(--border)',
                background: 'var(--surface)',
                textAlign: 'left',
                transition: 'background 0.1s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-raised)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface)')}
            >
              {isExpanded
                ? <ChevronDown size={13} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />
                : <ChevronRight size={13} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />
              }
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: 'var(--radius-full)',
                  background: `${topic.color}18`,
                  color: topic.color,
                }}
              >
                {topic.name}
              </span>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                {groupPrompts.length} prompts
              </span>
              <span style={{ marginLeft: 'auto', display: 'flex', gap: 16, fontSize: 12 }}>
                <span style={{ color: 'var(--text-secondary)' }}>
                  Avg Mention: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{(topic.avgMentionRate * 100).toFixed(1)}%</span>
                </span>
                <span style={{ color: 'var(--text-secondary)' }}>
                  Avg Citation: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{(topic.avgCitationRate * 100).toFixed(1)}%</span>
                </span>
              </span>
            </button>

            {/* Expanded rows */}
            {isExpanded && (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <tbody>
                  {groupPrompts.map((p) => (
                    <PromptTableRow key={p.id} prompt={p} onClick={() => onRowClick(p)} />
                  ))}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
    </div>
  );
}
