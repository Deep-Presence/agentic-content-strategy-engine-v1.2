import type { SSEEventType } from "@/types/api";
import { ALL_SSE_EVENTS, TERMINAL_SSE_EVENTS } from "./constants";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function streamTaskEvents(
  taskId: string,
  onEvent: (type: SSEEventType, data: Record<string, any>) => void,
  onDone?: () => void,
): EventSource {
  const url = `${API_BASE}/api/v1/tasks/${taskId}/events`;
  const es = new EventSource(url);

  for (const type of ALL_SSE_EVENTS) {
    es.addEventListener(type, (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      onEvent(type, data);

      if (TERMINAL_SSE_EVENTS.includes(type)) {
        es.close();
        onDone?.();
      }
    });
  }

  es.onerror = () => {
    console.warn("[SSE] Connection error — browser will auto-reconnect");
  };

  return es;
}
