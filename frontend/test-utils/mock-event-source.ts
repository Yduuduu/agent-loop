import type { EventSourceConstructor } from "@/lib/sse-client";

type Listener = (event: MessageEvent | Event) => void;

/** 실제 네트워크 없이 백엔드 SSE 스트림을 흉내 내는 테스트용 EventSource.
 * 실제 EventSource의 addEventListener 오버로드 타입까지 맞추지 않고,
 * export 지점(mockEventSourceConstructor)에서 필요한 형태로 캐스팅한다. */
export class MockEventSource {
  static instances: MockEventSource[] = [];

  url: string;
  closed = false;
  private listeners: Record<string, Listener[]> = {};

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  static reset() {
    MockEventSource.instances = [];
  }

  static last(): MockEventSource {
    const instance = MockEventSource.instances.at(-1);
    if (!instance) throw new Error("MockEventSource가 아직 생성되지 않았습니다");
    return instance;
  }

  addEventListener(type: string, listener: EventListener) {
    (this.listeners[type] ??= []).push(listener as Listener);
  }

  removeEventListener() {
    // 테스트에서는 사용하지 않는다.
  }

  close() {
    this.closed = true;
  }

  /** 서버가 `event: <type>\ndata: <json>`을 보낸 것처럼 흉내 낸다. */
  emit(type: string, data: unknown) {
    const event = { type, data: JSON.stringify(data) } as MessageEvent;
    this.listeners[type]?.forEach((listener) => listener(event));
  }

  /** 네트워크 연결 자체의 실패(.data 없는 plain Event)를 흉내 낸다. */
  emitConnectionError() {
    const event = { type: "error" } as Event;
    this.listeners["error"]?.forEach((listener) => listener(event));
  }
}

export const mockEventSourceConstructor = MockEventSource as unknown as EventSourceConstructor;
