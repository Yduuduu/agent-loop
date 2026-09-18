"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { useRefundCase } from "@/hooks/use-refund-cases";
import { connectRefundStream, type EventSourceConstructor } from "@/lib/sse-client";
import { useRefundStreamStore } from "@/store/refund-stream-store";

import { AgentViewer } from "./agent-viewer";

const STATUS_LABELS: Record<string, string> = {
  pending: "대기",
  in_progress: "처리 중",
  awaiting_human: "사람 검토 대기",
  completed: "완료",
  failed: "실패",
};

const DECISION_LABELS: Record<string, string> = {
  approve: "승인",
  reject: "거절",
  needs_human: "사람 검토 필요",
  resolved: "관리자 직접 처리",
};

interface AgentViewerStreamProps {
  caseId: string;
  /** 테스트에서 mock EventSource를 주입하기 위한 훅. */
  eventSourceImpl?: EventSourceConstructor;
}

export function AgentViewerStream({ caseId, eventSourceImpl }: AgentViewerStreamProps) {
  const connectionStatus = useRefundStreamStore((s) => s.connectionStatus);
  const currentNode = useRefundStreamStore((s) => s.currentNode);
  const completedNodes = useRefundStreamStore((s) => s.completedNodes);
  const latestDecision = useRefundStreamStore((s) => s.latestDecision);
  const awaitingHuman = useRefundStreamStore((s) => s.awaitingHuman);
  const errorMessage = useRefundStreamStore((s) => s.errorMessage);
  const queryClient = useQueryClient();
  // 이미 완료된 케이스를 재방문하면 스트림 큐가 소비되어 있어 재연결이 안 된다
  // (백엔드가 410 반환). 그 경우 라이브 뷰어 대신 DB에 남아있는 최종 상태를
  // 보여준다 — useRefundCase는 상세 페이지와 같은 쿼리 키를 써서 캐시를 공유한다.
  const { data: caseData } = useRefundCase(caseId);
  const hasLiveData = currentNode !== null || completedNodes.length > 0 || awaitingHuman !== null || latestDecision !== null;
  const streamUnavailable = connectionStatus === "unavailable" && !hasLiveData;

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
        // 네트워크 순단 등으로 연결이 잠깐 끊긴 경우 네이티브 EventSource가
        // 자체적으로 재연결을 시도한다. 반면 큐가 아예 없는 경우(410, 이미
        // 소비됨/시작된 적 없음)는 서버가 비-200을 반환해 브라우저가 재시도 없이
        // 연결을 영구 종료하므로, 이때만 "unavailable"로 표시해 정적 요약으로
        // 전환한다.
        onConnectionError: () => useRefundStreamStore.getState().handleConnectionUnavailable(),
      },
      eventSourceImpl ? { EventSourceImpl: eventSourceImpl } : undefined,
    );

    return disconnect;
  }, [caseId, eventSourceImpl, queryClient]);

  if (streamUnavailable) {
    return <StaticCaseSummary caseData={caseData} />;
  }

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

function StaticCaseSummary({ caseData }: { caseData: ReturnType<typeof useRefundCase>["data"] }) {
  return (
    <div className="flex flex-col gap-3">
      <span className="w-fit rounded-full border border-border-subtle px-2 py-0.5 text-xs text-text-secondary">
        실시간 로그 없음 (이전에 종료된 실행)
      </span>
      <div className="rounded-md border border-border-subtle bg-surface-2 p-3 text-sm">
        <p className="text-text-secondary">
          이 케이스의 추론 과정은 이미 종료되어 다시 재생할 수 없습니다. 아래는 저장된 최종 상태입니다.
        </p>
        {caseData ? (
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
            <dt className="text-text-secondary">상태</dt>
            <dd>{STATUS_LABELS[caseData.status] ?? caseData.status}</dd>
            {caseData.decision && (
              <>
                <dt className="text-text-secondary">최종 판정</dt>
                <dd>{DECISION_LABELS[caseData.decision] ?? caseData.decision}</dd>
              </>
            )}
            {caseData.decision_reason && (
              <>
                <dt className="text-text-secondary">판정 사유</dt>
                <dd>{caseData.decision_reason}</dd>
              </>
            )}
            {caseData.flagged_reason && (
              <>
                <dt className="text-text-secondary">플래그 사유</dt>
                <dd>{caseData.flagged_reason}</dd>
              </>
            )}
          </dl>
        ) : (
          <p className="mt-2 text-text-secondary">불러오는 중...</p>
        )}
      </div>
    </div>
  );
}
