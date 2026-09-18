import { beforeEach, describe, expect, it } from "vitest";

import { useRefundStreamStore } from "./refund-stream-store";

beforeEach(() => {
  useRefundStreamStore.setState(useRefundStreamStore.getInitialState());
});

describe("useRefundStreamStore", () => {
  it("accumulates completed nodes and tracks the current node across events", () => {
    const store = useRefundStreamStore.getState();
    store.startStream("case-1");
    store.handleNodeStart({ case_id: "case-1", node: "order_lookup" });
    expect(useRefundStreamStore.getState().currentNode).toBe("order_lookup");

    store.handleToolCall({ case_id: "case-1", node: "order_lookup", summary: "조회 완료" });
    const afterToolCall = useRefundStreamStore.getState();
    expect(afterToolCall.completedNodes).toEqual(["order_lookup"]);
    expect(afterToolCall.currentNode).toBeNull();
    expect(afterToolCall.toolCallLog).toHaveLength(1);

    store.handleNodeStart({ case_id: "case-1", node: "damage_assessment" });
    store.handleNodeEnd({ case_id: "case-1", node: "damage_assessment", summary: "판정 완료" });
    const afterNodeEnd = useRefundStreamStore.getState();
    expect(afterNodeEnd.completedNodes).toEqual(["order_lookup", "damage_assessment"]);
  });

  it("ignores duplicate node_end events for the same node (dedup safety)", () => {
    const store = useRefundStreamStore.getState();
    store.startStream("case-1");
    store.handleNodeEnd({ case_id: "case-1", node: "decision", summary: "x" });
    store.handleNodeEnd({ case_id: "case-1", node: "decision", summary: "x" });

    expect(useRefundStreamStore.getState().completedNodes).toEqual(["decision"]);
  });

  it("ignores events for a stale case_id after a new stream has started (out-of-order safety)", () => {
    const store = useRefundStreamStore.getState();
    store.startStream("case-old");
    store.handleNodeStart({ case_id: "case-old", node: "order_lookup" });

    // 재연결로 새 스트림이 시작됨 — 이전 상태는 리셋된다.
    store.startStream("case-new");
    expect(useRefundStreamStore.getState().currentNode).toBeNull();

    // 이전 케이스의 지연된 이벤트가 뒤늦게 도착해도 새 스트림 상태를 건드리지 않는다.
    store.handleNodeStart({ case_id: "case-old", node: "damage_assessment" });
    expect(useRefundStreamStore.getState().currentNode).toBeNull();
    expect(useRefundStreamStore.getState().caseId).toBe("case-new");
  });

  it("records a terminal decision and clears the current node", () => {
    const store = useRefundStreamStore.getState();
    store.startStream("case-1");
    store.handleNodeStart({ case_id: "case-1", node: "decision" });
    store.handleDecision({
      case_id: "case-1",
      decision: "approve",
      reason: "반품 기한 내 파손 확인",
      requires_human: false,
    });

    const state = useRefundStreamStore.getState();
    expect(state.latestDecision?.decision).toBe("approve");
    expect(state.currentNode).toBeNull();
  });

  it("records awaiting_human separately from a final decision", () => {
    const store = useRefundStreamStore.getState();
    store.startStream("case-1");
    store.handleAwaitingHuman({
      case_id: "case-1",
      reason: "고액 환불",
      suggested_decision: "approve",
    });

    const state = useRefundStreamStore.getState();
    expect(state.awaitingHuman?.reason).toBe("고액 환불");
    expect(state.latestDecision).toBeNull();
  });
});
