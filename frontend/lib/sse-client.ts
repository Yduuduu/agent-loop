import { refundStreamUrl } from "@/lib/api-client";
import type {
  AwaitingHumanData,
  DecisionData,
  ErrorData,
  NodeEndData,
  NodeStartData,
  SSEEventType,
  ToolCallData,
} from "@/lib/types";

export interface RefundStreamHandlers {
  onOpen?: () => void;
  onNodeStart?: (data: NodeStartData) => void;
  onNodeEnd?: (data: NodeEndData) => void;
  onToolCall?: (data: ToolCallData) => void;
  onDecision?: (data: DecisionData) => void;
  onAwaitingHuman?: (data: AwaitingHumanData) => void;
  /** 백엔드가 명시적으로 보낸 `event: error` (애플리케이션 레벨). */
  onErrorEvent?: (data: ErrorData) => void;
  /** 네트워크 끊김 등 EventSource 자체의 연결 오류(자동 재연결 대상). */
  onConnectionError?: (event: Event) => void;
}

// 이 4개 타입이 도착하면 이번 스트림 레그는 끝난다 — decision/error는 케이스
// 자체가 끝난 것이고, awaiting_human은 재개 전까지 더 올 이벤트가 없다.
const TERMINAL_EVENT_TYPES: SSEEventType[] = ["decision", "error", "awaiting_human"];

export type MinimalEventSource = Pick<EventSource, "addEventListener" | "close">;
export type EventSourceConstructor = new (url: string) => MinimalEventSource;

/**
 * 케이스 SSE 스트림에 연결한다. 반환된 함수를 호출하면 연결을 정리한다
 * (컴포넌트 언마운트 시 반드시 호출해야 함).
 */
export function connectRefundStream(
  caseId: string,
  handlers: RefundStreamHandlers,
  options?: { EventSourceImpl?: EventSourceConstructor },
): () => void {
  const EventSourceImpl =
    options?.EventSourceImpl ?? (EventSource as unknown as EventSourceConstructor);
  const source = new EventSourceImpl(refundStreamUrl(caseId));

  const listen = <T>(type: SSEEventType, handler?: (data: T) => void) => {
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

  source.addEventListener("open", () => handlers.onOpen?.());
  listen<NodeStartData>("node_start", handlers.onNodeStart);
  listen<NodeEndData>("node_end", handlers.onNodeEnd);
  listen<ToolCallData>("tool_call", handlers.onToolCall);
  listen<DecisionData>("decision", handlers.onDecision);
  listen<AwaitingHumanData>("awaiting_human", handlers.onAwaitingHuman);

  // "error"는 EventSource에서 두 가지 의미로 겹친다: 서버가 보낸 `event: error`
  // 메시지(MessageEvent, .data 있음)와 네트워크 연결 자체의 실패(plain Event,
  // .data 없음 — 브라우저가 자동 재연결을 시도한다). .data 유무로 구분한다.
  source.addEventListener("error", (event) => {
    const raw = (event as MessageEvent).data;
    if (typeof raw === "string") {
      let data: ErrorData;
      try {
        data = JSON.parse(raw) as ErrorData;
      } catch {
        return;
      }
      handlers.onErrorEvent?.(data);
      source.close();
    } else {
      handlers.onConnectionError?.(event);
    }
  });

  return () => source.close();
}
