import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useRefundStreamStore } from "@/store/refund-stream-store";
import { MockEventSource, mockEventSourceConstructor } from "@/test-utils/mock-event-source";

import { AgentViewerStream } from "./agent-viewer-stream";

beforeEach(() => {
  MockEventSource.reset();
  useRefundStreamStore.setState(useRefundStreamStore.getInitialState());
});

describe("AgentViewerStream", () => {
  it("renders the pipeline live as a mocked SSE event sequence arrives", () => {
    render(<AgentViewerStream caseId="case-1" eventSourceImpl={mockEventSourceConstructor} />);

    const source = MockEventSource.last();

    act(() => source.emit("node_start", { case_id: "case-1", node: "order_lookup" }));
    expect(screen.getByText("주문 내역 조회 중...")).toBeInTheDocument();

    act(() =>
      source.emit("tool_call", {
        case_id: "case-1",
        node: "order_lookup",
        summary: "주문 내역 조회 완료: ORD-1001",
      }),
    );
    expect(screen.getByText("주문 내역 조회 완료")).toBeInTheDocument();
    expect(screen.getByText(/주문 내역 조회 완료: ORD-1001/)).toBeInTheDocument();

    act(() => source.emit("node_start", { case_id: "case-1", node: "damage_assessment" }));
    expect(screen.getByText("파손 여부 판정 중...")).toBeInTheDocument();

    act(() =>
      source.emit("node_end", {
        case_id: "case-1",
        node: "damage_assessment",
        summary: "파손 판정 완료",
      }),
    );

    act(() =>
      source.emit("decision", {
        case_id: "case-1",
        decision: "approve",
        reason: "반품 기한 내 파손이 확인되었습니다.",
        requires_human: false,
      }),
    );

    expect(screen.getByText("최종 판정: approve")).toBeInTheDocument();
    expect(screen.getByText("반품 기한 내 파손이 확인되었습니다.")).toBeInTheDocument();
    expect(source.closed).toBe(true);
  });

  it("shows an awaiting_human banner and stops without a final decision", () => {
    render(<AgentViewerStream caseId="case-2" eventSourceImpl={mockEventSourceConstructor} />);
    const source = MockEventSource.last();

    act(() =>
      source.emit("awaiting_human", {
        case_id: "case-2",
        reason: "환불 금액이 고액 기준을 초과했습니다.",
        suggested_decision: "approve",
      }),
    );

    expect(screen.getByText("사람 검토 대기 중")).toBeInTheDocument();
    expect(screen.getByText("환불 금액이 고액 기준을 초과했습니다.")).toBeInTheDocument();
    expect(screen.queryByText(/최종 판정:/)).not.toBeInTheDocument();
  });

  it("surfaces an application-level error event", () => {
    render(<AgentViewerStream caseId="case-3" eventSourceImpl={mockEventSourceConstructor} />);
    const source = MockEventSource.last();

    act(() =>
      source.emit("error", { case_id: "case-3", message: "주문을 찾을 수 없습니다: ORD-NOPE" }),
    );

    expect(screen.getByText("오류 발생")).toBeInTheDocument();
    expect(screen.getByText("주문을 찾을 수 없습니다: ORD-NOPE")).toBeInTheDocument();
  });

  it("ignores out-of-order events left over from a previous case", () => {
    const { rerender } = render(
      <AgentViewerStream caseId="case-old" eventSourceImpl={mockEventSourceConstructor} />,
    );
    const oldSource = MockEventSource.last();
    act(() => oldSource.emit("node_start", { case_id: "case-old", node: "order_lookup" }));

    rerender(<AgentViewerStream caseId="case-new" eventSourceImpl={mockEventSourceConstructor} />);

    // 재연결 후에도 이전 소스로 뒤늦게 도착한 이벤트가 새 케이스 상태를 오염시키지 않는다.
    // (pending 단계도 "~하는 중" 라벨을 회색으로 보여주므로 텍스트가 아니라
    // data-status로 검증한다 — 텍스트만 보면 pending과 in_progress를 구분 못 한다.)
    act(() => oldSource.emit("node_start", { case_id: "case-old", node: "damage_assessment" }));

    const damageAssessmentStep = document.querySelector('[data-node="damage_assessment"]');
    expect(damageAssessmentStep).toHaveAttribute("data-status", "pending");
  });
});
