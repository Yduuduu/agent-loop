import { kbDocumentStreamUrl } from "@/lib/api-client";
import type { EventSourceConstructor } from "@/lib/sse-client";
import type { KBEventType, KBFailedData, KBProgressData } from "@/lib/types";

export interface KbStreamHandlers {
  onChunking?: (data: KBProgressData) => void;
  onEmbedding?: (data: KBProgressData) => void;
  onIndexed?: (data: KBProgressData) => void;
  // KB 이벤트는 실패를 "error"가 아니라 "failed"로 보내므로(백엔드
  // app/api/schemas/kb_events.py), refund SSE와 달리 네이티브 EventSource의
  // 예약된 "error" 타입과 이름이 겹치지 않는다 — 연결 오류와 헷갈릴 일이 없다.
  onFailed?: (data: KBFailedData) => void;
}

const TERMINAL_EVENT_TYPES: KBEventType[] = ["indexed", "failed"];

/** 지식베이스 문서 인제스천 SSE 스트림에 연결한다. 반환된 함수로 정리한다. */
export function connectKbDocumentStream(
  docId: string,
  handlers: KbStreamHandlers,
  options?: { EventSourceImpl?: EventSourceConstructor },
): () => void {
  const EventSourceImpl =
    options?.EventSourceImpl ?? (EventSource as unknown as EventSourceConstructor);
  const source = new EventSourceImpl(kbDocumentStreamUrl(docId));

  const listen = <T>(type: KBEventType, handler?: (data: T) => void) => {
    source.addEventListener(type, (event) => {
      const raw = (event as MessageEvent).data;
      if (typeof raw !== "string") return;

      let data: T;
      try {
        data = JSON.parse(raw) as T;
      } catch {
        return;
      }

      handler?.(data);
      if (TERMINAL_EVENT_TYPES.includes(type)) {
        source.close();
      }
    });
  };

  listen<KBProgressData>("chunking", handlers.onChunking);
  listen<KBProgressData>("embedding", handlers.onEmbedding);
  listen<KBProgressData>("indexed", handlers.onIndexed);
  listen<KBFailedData>("failed", handlers.onFailed);

  return () => source.close();
}
