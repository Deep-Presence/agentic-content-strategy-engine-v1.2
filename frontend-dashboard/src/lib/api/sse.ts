const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function createEventStream(
  taskId: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  onError?: (error: Event) => void
): () => void {
  const es = new EventSource(`${API_BASE}/api/v1/tasks/${taskId}/events`);

  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onEvent(data.event || event.type, data);
    } catch {
      // Heartbeat or non-JSON message, ignore
    }
  };

  es.onerror = (err) => {
    onError?.(err);
  };

  return () => es.close();
}
