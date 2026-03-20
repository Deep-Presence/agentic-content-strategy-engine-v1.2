import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useTaskStream } from '@/lib/hooks/useTaskStream';

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  apiPost: vi.fn(),
}));

import { apiPost } from '@/lib/api/client';

// Mock EventSource as a proper class that can be used with `new`
let mockInstance: InstanceType<typeof MockEventSourceClass> | null = null;

class MockEventSourceClass {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  url: string;
  readyState = MockEventSourceClass.OPEN;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  private listeners: Record<string, ((e: MessageEvent) => void)[]> = {};

  constructor(url: string) {
    this.url = url;
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    mockInstance = this;
  }

  addEventListener(type: string, listener: (e: MessageEvent) => void) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  removeEventListener(type: string, listener: (e: MessageEvent) => void) {
    if (this.listeners[type]) {
      this.listeners[type] = this.listeners[type].filter(l => l !== listener);
    }
  }

  close() {
    this.readyState = MockEventSourceClass.CLOSED;
  }

  // Test helper: simulate receiving a named SSE event
  _emit(type: string, data: Record<string, unknown>) {
    const event = new MessageEvent(type, { data: JSON.stringify(data) });
    if (this.listeners[type]) {
      for (const listener of this.listeners[type]) {
        listener(event);
      }
    }
  }
}

beforeEach(() => {
  mockInstance = null;
  vi.clearAllMocks();
  // Replace global EventSource with our mock class
  (globalThis as Record<string, unknown>).EventSource = MockEventSourceClass;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useTaskStream', () => {
  it('returns idle status when taskId is null', () => {
    const { result } = renderHook(() => useTaskStream(null));
    expect(result.current.status).toBe('idle');
    expect(result.current.events).toEqual([]);
    expect(result.current.currentStep).toBeNull();
    expect(result.current.progressPct).toBe(0);
  });

  it('requests stream token and opens EventSource', async () => {
    vi.mocked(apiPost).mockResolvedValueOnce({
      stream_token: 'st-123',
      expires_in: 300,
    });

    const { result } = renderHook(() => useTaskStream('task-abc'));

    await waitFor(() => {
      expect(apiPost).toHaveBeenCalledWith('/api/v1/tasks/task-abc/stream-token', {});
    });

    await waitFor(() => {
      expect(result.current.status).toBe('connected');
    });

    expect(mockInstance).not.toBeNull();
    expect(mockInstance!.url).toContain('stream_token=st-123');
  });

  it('accumulates events and updates currentStep on progress', async () => {
    vi.mocked(apiPost).mockResolvedValueOnce({ stream_token: 'st-1', expires_in: 300 });

    const { result } = renderHook(() => useTaskStream('task-1'));
    await waitFor(() => expect(result.current.status).toBe('connected'));

    act(() => {
      mockInstance!._emit('onboarding_phase_start', { phase: 'phase_a', message: 'Phase A' });
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0].type).toBe('onboarding_phase_start');

    act(() => {
      mockInstance!._emit('progress', { step: 'site_audit', progress_pct: 25 });
    });

    expect(result.current.currentStep).toBe('site_audit');
    expect(result.current.progressPct).toBe(25);
  });

  it('sets completed status on terminal event', async () => {
    vi.mocked(apiPost).mockResolvedValueOnce({ stream_token: 'st-1', expires_in: 300 });

    const { result } = renderHook(() => useTaskStream('task-2'));
    await waitFor(() => expect(result.current.status).toBe('connected'));

    act(() => {
      mockInstance!._emit('completed', { status: 'completed' });
    });

    expect(result.current.status).toBe('completed');
    expect(result.current.progressPct).toBe(100);
  });

  it('sets error status on failed event', async () => {
    vi.mocked(apiPost).mockResolvedValueOnce({ stream_token: 'st-1', expires_in: 300 });

    const { result } = renderHook(() => useTaskStream('task-3'));
    await waitFor(() => expect(result.current.status).toBe('connected'));

    act(() => {
      mockInstance!._emit('failed', { error: 'KB agent crashed' });
    });

    expect(result.current.status).toBe('error');
    expect(result.current.error).toBe('KB agent crashed');
  });

  it('closes EventSource on unmount', async () => {
    vi.mocked(apiPost).mockResolvedValueOnce({ stream_token: 'st-1', expires_in: 300 });

    const { result, unmount } = renderHook(() => useTaskStream('task-4'));
    await waitFor(() => expect(result.current.status).toBe('connected'));

    unmount();
    expect(mockInstance!.readyState).toBe(MockEventSourceClass.CLOSED);
  });

  it('tracks onboarding_sub_start as currentStep', async () => {
    vi.mocked(apiPost).mockResolvedValueOnce({ stream_token: 'st-1', expires_in: 300 });

    const { result } = renderHook(() => useTaskStream('task-5'));
    await waitFor(() => expect(result.current.status).toBe('connected'));

    act(() => {
      mockInstance!._emit('onboarding_sub_start', { pipeline: 'knowledge_base' });
    });

    expect(result.current.currentStep).toBe('knowledge_base');
  });
});
