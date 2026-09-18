"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { connectRefundStream, type EventSourceConstructor } from "@/lib/sse-client";
import { useRefundStreamStore } from "@/store/refund-stream-store";

import { AgentViewer } from "./agent-viewer";

interface AgentViewerStreamProps {
  caseId: string;
  /** 테스트에서 mock EventSource를 주입하기 위한 훅. */
  eventSourceImpl?: EventSourceConstructor;
}

export function AgentViewerStream({ caseId, eventSourceImpl }: AgentViewerStreamProps) {
  const connectionStatus = useRefundStreamStore((s) => s.connectionStatus);
  const latestDecision = useRefundStreamStore((s) => s.latestDecision);
  const awaitingHuman = useRefundStreamStore((s) => s.awaitingHuman);
  const errorMessage = useRefundStreamStore((s) => s.errorMessage);
  const queryClient = useQueryClient();

  useEffect(() => {
    const store = useRefundStreamStore.getState();
    store.startStream(caseId);

    // 종료성 이벤트가 오면 케이스 메타데이터(React Query)도 즉시 다시 불러온다.
    // 4초 폴링만 믿으면 "최종 판정" 배너는 즉시 뜨는데 상단 "상태" 필드는
    // 몇 초간 낡은 값(예: 처리 중)을 보여주는 어색한 텀이 생긴다.
    const refetchCaseMetadata = () =>
      queryClient.invalidateQueries({ queryKey: ["refund-case", caseId] });

    const disconnect = connectRefundStream(
      caseId,
      {
        onOpen: () => useRefundStreamStore.getState().handleConnectionOpen(),
        onNodeStart: (data) => useRefundStreamStore.getState().handleNodeStart(data),
        onNodeEnd: (data) => useRefundStreamStore.getState().handleNodeEnd(data),
        onToolCall: (data) => useRefundStreamStore.getState().handleToolCall(data),
        onDecision: (data) => {
          useRefundStreamStore.getState().handleDecision(data);
          useRefundStreamStore.getState().handleConnectionClosed();
          refetchCaseMetadata();
        },
        onAwaitingHuman: (data) => {
          useRefundStreamStore.getState().handleAwaitingHuman(data);
          useRefundStreamStore.getState().handleConnectionClosed();
          refetchCaseMetadata();
        },
        onErrorEvent: (data) => {
          useRefundStreamStore.getState().handleErrorEvent(data);
          useRefundStreamStore.getState().handleConnectionClosed();
          refetchCaseMetadata();
        },
        // 네이티브 EventSource가 자체적으로 재연결을 시도한다. 연결이 완전히
        // 끊기면 케이스 상세 페이지의 React Query 폴링(useRefundCase)이
        // 진실의 원천 역할을 대신한다 — 여기서는 별도 처리가 필요 없다.
      },
      eventSourceImpl ? { EventSourceImpl: eventSourceImpl } : undefined,
    );

    return disconnect;
  }, [caseId, eventSourceImpl, queryClient]);

  return (
    <div className="flex flex-col gap-4">
      <ConnectionBadge status={connectionStatus} />
      <AgentViewer />
      {awaitingHuman && (
        <div className="rounded-md border border-status-progress/30 bg-status-progress/10 p-3 text-sm">
          <p className="font-medium text-foreground">사람 검토 대기 중</p>
          <p className="mt-1 text-text-secondary">{awaitingHuman.reason}</p>
        </div>
      )}
      {latestDecision && (
        <div className="rounded-md border border-status-good/30 bg-status-good/10 p-3 text-sm">
          <p className="font-medium text-foreground">최종 판정: {latestDecision.decision}</p>
          {latestDecision.reason && (
            <p className="mt-1 text-text-secondary">{latestDecision.reason}</p>
          )}
        </div>
      )}
      {errorMessage && (
        <div className="rounded-md border border-status-critical/30 bg-status-critical/10 p-3 text-sm">
          <p className="font-medium text-status-critical">오류 발생</p>
          <p className="mt-1 text-text-secondary">{errorMessage}</p>
        </div>
      )}
    </div>
  );
}

function ConnectionBadge({ status }: { status: string }) {
  const label =
    status === "open"
      ? "실시간 연결됨"
      : status === "connecting"
        ? "연결 중..."
        : status === "closed"
          ? "연결 종료"
          : "대기 중";

  return (
    <span className="w-fit rounded-full border border-border-subtle px-2 py-0.5 text-xs text-text-secondary">
      {label}
    </span>
  );
}
