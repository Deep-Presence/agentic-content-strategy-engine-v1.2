'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { tasks } from '@/lib/api/tasks';
import type { TaskResponse } from '@/types/common';

interface UseTasksOptions {
  status?: string;
  pollInterval?: number;
  autoRefresh?: boolean;
}

interface UseTasksResult {
  tasks: TaskResponse[];
  total: number;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useTasks(options: UseTasksOptions = {}): UseTasksResult {
  const { status, pollInterval = 5000, autoRefresh = true } = options;
  const [taskList, setTaskList] = useState<TaskResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchTasks = useCallback(async () => {
    try {
      const result = await tasks.list(status ? { status } : undefined);
      setTaskList(result.tasks);
      setTotal(result.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch tasks');
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    fetchTasks();

    if (autoRefresh) {
      const hasRunning = taskList.some((t) => t.status === 'running');
      if (hasRunning || loading) {
        intervalRef.current = setInterval(fetchTasks, pollInterval);
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchTasks, autoRefresh, pollInterval, taskList, loading]);

  return { tasks: taskList, total, loading, error, refresh: fetchTasks };
}
