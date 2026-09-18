"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { AgentViewerStream } from "@/components/agent-viewer/agent-viewer-stream";
import { useRefundCase } from "@/hooks/use-refund-cases";

const STATUS_LABELS: Record<string, string> = {
  pending: "대기",
  in_progress: "처리 중",
  awaiting_human: "사람 검토 대기",
  completed: "완료",
  failed: "실패",
};

export default function RefundCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: caseData, isLoading, error } = useRefundCase(id);

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

      <section>
        <h2 className="mb-3 text-sm font-medium text-text-secondary">에이전트 추론 과정</h2>
        {id && <AgentViewerStream caseId={id} />}
      </section>
    </div>
  );
}
