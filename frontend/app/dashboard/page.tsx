"use client";

import Link from "next/link";

import { useRefundCases } from "@/hooks/use-refund-cases";
import { formatElapsed } from "@/lib/format-elapsed";
import { sortByAwaitingSince } from "@/lib/sort-queue";

const STATUS_LABELS: Record<string, string> = {
  pending: "대기",
  in_progress: "처리 중",
  awaiting_human: "사람 검토 대기",
  completed: "완료",
  failed: "실패",
};

export default function DashboardPage() {
  const { data: allCases, isLoading, error } = useRefundCases();
  const { data: queueCases } = useRefundCases("awaiting_human");
  const queue = queueCases ? sortByAwaitingSince(queueCases) : [];

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-6 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">환불 케이스 대시보드</h1>
        <div className="flex items-center gap-3">
          <Link
            href="/knowledge-base"
            className="text-sm text-text-secondary hover:text-foreground"
          >
            지식베이스
          </Link>
          <Link
            href="/refund-cases"
            className="rounded-md bg-status-progress px-3 py-1.5 text-sm font-medium text-white"
          >
            새 요청
          </Link>
        </div>
      </div>

      {queue.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-medium text-text-secondary">
            사람 검토 대기 중 ({queue.length}건 — 오래 기다린 순)
          </h2>
          <ul className="flex flex-col gap-2">
            {queue.map((c) => (
              <li key={c.case_id}>
                <Link
                  href={`/refund-cases/${c.case_id}`}
                  className="flex flex-col gap-1 rounded-md border border-status-progress/30 bg-status-progress/5 px-4 py-3 text-sm hover:bg-status-progress/10"
                >
                  <div className="flex items-center justify-between gap-4">
                    <span className="font-medium">{c.order_id}</span>
                    <div className="flex items-center gap-3 text-text-secondary">
                      {c.refund_amount != null && <span>${c.refund_amount.toFixed(2)}</span>}
                      {c.awaiting_human_since && (
                        <span>{formatElapsed(c.awaiting_human_since)}</span>
                      )}
                    </div>
                  </div>
                  {c.flagged_reason && (
                    <p className="line-clamp-2 text-text-secondary">{c.flagged_reason}</p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2 className="mb-3 text-sm font-medium text-text-secondary">전체 케이스</h2>

        {isLoading && <p className="text-sm text-text-secondary">불러오는 중...</p>}
        {error && (
          <p className="text-sm text-status-critical">케이스 목록을 불러오지 못했습니다.</p>
        )}

        {allCases && allCases.length === 0 && (
          <p className="text-sm text-text-secondary">아직 생성된 케이스가 없습니다.</p>
        )}

        {allCases && allCases.length > 0 && (
          <ul className="flex flex-col divide-y divide-border-subtle rounded-md border border-border-subtle">
            {allCases.map((c) => (
              <li key={c.case_id}>
                <Link
                  href={`/refund-cases/${c.case_id}`}
                  className="flex items-center justify-between gap-4 px-4 py-3 text-sm hover:bg-surface-2"
                >
                  <span className="font-mono text-xs text-text-secondary">
                    {c.case_id.slice(0, 8)}
                  </span>
                  <span>{c.order_id}</span>
                  <span className="text-text-secondary">{STATUS_LABELS[c.status] ?? c.status}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
