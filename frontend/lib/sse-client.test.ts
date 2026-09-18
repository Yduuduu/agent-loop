import { beforeEach, describe, expect, it, vi } from "vitest";

import { MockEventSource, mockEventSourceConstructor } from "@/test-utils/mock-event-source";

import { connectRefundStream } from "./sse-client";

beforeEach(() => {
  MockEventSource.reset();
});

describe("connectRefundStream", () => {
  it("dispatches node_start/tool_call/node_end/decision in order and closes on decision", () => {
    const events: string[] = [];
    const disconnect = connectRefundStream(
      "case-1",
      {
        onNodeStart: (d) => events.push(`node_start:${d.node}`),
        onToolCall: (d) => events.push(`tool_call:${d.node}`),
        onNodeEnd: (d) => events.push(`node_end:${d.node}`),
        onDecision: (d) => events.push(`decision:${d.decision}`),
      },
      { EventSourceImpl: mockEventSourceConstructor },
    );

    const source = MockEventSource.last();
    source.emit("node_start", { case_id: "case-1", node: "order_lookup" });
    source.emit("tool_call", { case_id: "case-1", node: "order_lookup", summary: "조회 완료" });
    source.emit("node_start", { case_id: "case-1", node: "damage_assessment" });
    source.emit("node_end", { case_id: "case-1", node: "damage_assessment", summary: "판정 완료" });
    source.emit("decision", {
      case_id: "case-1",
      decision: "approve",
      reason: "ok",
      requires_human: false,
    });

    expect(events).toEqual([
      "node_start:order_lookup",
      "tool_call:order_lookup",
      "node_start:damage_assessment",
      "node_end:damage_assessment",
      "decision:approve",
    ]);
    expect(source.closed).toBe(true);

    disconnect();
  });

  it("closes the stream on awaiting_human without requiring a decision event", () => {
    const onAwaitingHuman = vi.fn();
    connectRefundStream(
      "case-2",
      { onAwaitingHuman },
      { EventSourceImpl: mockEventSourceConstructor },
    );

    const source = MockEventSource.last();
    source.emit("awaiting_human", {
      case_id: "case-2",
      reason: "고액",
      suggested_decision: "approve",
    });

    expect(onAwaitingHuman).toHaveBeenCalledWith({
      case_id: "case-2",
      reason: "고액",
      suggested_decision: "approve",
    });
    expect(source.closed).toBe(true);
  });

  it("routes an application-level error event to onErrorEvent and closes the stream", () => {
    const onErrorEvent = vi.fn();
    const onConnectionError = vi.fn();
    connectRefundStream(
      "case-3",
      { onErrorEvent, onConnectionError },
      { EventSourceImpl: mockEventSourceConstructor },
    );

    const source = MockEventSource.last();
    source.emit("error", { case_id: "case-3", message: "boom" });

    expect(onErrorEvent).toHaveBeenCalledWith({ case_id: "case-3", message: "boom" });
    expect(onConnectionError).not.toHaveBeenCalled();
    expect(source.closed).toBe(true);
  });

  it("routes a native connection error (no .data) to onConnectionError without closing", () => {
    const onErrorEvent = vi.fn();
    const onConnectionError = vi.fn();
    connectRefundStream(
      "case-4",
      { onErrorEvent, onConnectionError },
      { EventSourceImpl: mockEventSourceConstructor },
    );

    const source = MockEventSource.last();
    source.emitConnectionError();

    expect(onConnectionError).toHaveBeenCalledTimes(1);
    expect(onErrorEvent).not.toHaveBeenCalled();
    // 네이티브 연결 오류는 브라우저가 알아서 재연결하므로 우리가 close()하지 않는다.
    expect(source.closed).toBe(false);
  });

  it("returns a cleanup function that closes the connection", () => {
    const disconnect = connectRefundStream(
      "case-5",
      {},
      { EventSourceImpl: mockEventSourceConstructor },
    );
    const source = MockEventSource.last();

    expect(source.closed).toBe(false);
    disconnect();
    expect(source.closed).toBe(true);
  });
});
