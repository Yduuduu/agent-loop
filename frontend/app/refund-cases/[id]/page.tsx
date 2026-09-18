"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { AgentViewerStream } from "@/components/agent-viewer/agent-viewer-stream";
import { HitlPanel } from "@/components/hitl/hitl-panel";
import { useRefundCase } from "@/hooks/use-refund-cases";

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

export default function RefundCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: caseData, isLoading, error } = useRefundCase(id);
  // resume 이후 SSE 스트림을 새로 여는 새 EventSource 연결이 필요하다(같은
  // caseId로는 useEffect 의존성이 안 바뀌므로) — key를 바꿔 컴포넌트를 통째로
  // 리마운트해 재연결을 강제한다.
  const [streamGeneration, setStreamGeneration] = useState(0);

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/dashboard" className="text-sm text-text-secondary hover:text-foreground">
        ← 대시보드로
      </Link>

      <div>
        <h1 className="text-xl font-semibold">환불 케이스 상세</h1>
        <p className="mt-1 font-mono text-sm text-text-secondary">{id}</p>
      </div>

      {isLoading && <p className="text-sm text-text-secondary">불러오는 중...</p>}
      {error && <p className="text-sm text-status-critical">케이스 정보를 불러오지 못했습니다.</p>}

      {caseData && (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-md border border-border-subtle bg-surface-2 p-4 text-sm">
          <dt className="text-text-secondary">주문 ID</dt>
          <dd>{caseData.order_id}</dd>
          <dt className="text-text-secondary">상태</dt>
          <dd>{STATUS_LABELS[caseData.status] ?? caseData.status}</dd>
          {caseData.refund_amount != null && (
            <>
              <dt className="text-text-secondary">환불 금액</dt>
              <dd>${caseData.refund_amount.toFixed(2)}</dd>
            </>
          )}
        </dl>
      )}

      {/* 상태 분기: in_progress(뷰어만) / awaiting_human(뷰어+HITL 패널) /
          completed·failed(뷰어+최종 요약). 이 요약은 React Query(폴링)를 그대로
          써서, SSE를 놓친 채(예: 완료된 케이스에 바로 들어온 경우) 페이지를 열어도
          항상 정확한 결과를 보여준다 — 실시간 이벤트 수신 여부에 기대지 않는다. */}
      {caseData?.status === "awaiting_human" && (
        <HitlPanel
          caseId={id}
          flaggedReason={caseData.flagged_reason}
          refundAmount={caseData.refund_amount}
          onResumed={() => setStreamGeneration((g) => g + 1)}
        />
      )}

      {caseData?.status === "completed" && (
        <div className="rounded-md border border-status-good/30 bg-status-good/10 p-4 text-sm">
          <p className="font-medium text-foreground">
            최종 판정:{" "}
            {caseData.decision ? (DECISION_LABELS[caseData.decision] ?? caseData.decision) : "-"}
          </p>
          {caseData.decision_reason && (
            <p className="mt-1 text-text-secondary">{caseData.decision_reason}</p>
          )}
        </div>
      )}

      {caseData?.status === "failed" && (
        <div className="rounded-md border border-status-critical/30 bg-status-critical/10 p-4 text-sm">
          <p className="font-medium text-status-critical">처리 중 오류가 발생했습니다.</p>
        </div>
      )}

      <section>
        <h2 className="mb-3 text-sm font-medium text-text-secondary">에이전트 추론 과정</h2>
        {id && <AgentViewerStream key={streamGeneration} caseId={id} />}
      </section>
    </div>
  );
}
