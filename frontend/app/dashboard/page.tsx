"use client";

import Link from "next/link";

import { useRefundCases } from "@/hooks/use-refund-cases";

const STATUS_LABELS: Record<string, string> = {
  pending: "대기",
  in_progress: "처리 중",
  awaiting_human: "사람 검토 대기",
  completed: "완료",
  failed: "실패",
};

// Phase 5에서 HITL 대기열 전용 뷰/필터/정렬로 확장될 최소 골격.
export default function DashboardPage() {
  const { data: cases, isLoading, error } = useRefundCases();

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">환불 케이스 대시보드</h1>
        <Link
          href="/refund-cases"
          className="rounded-md bg-status-progress px-3 py-1.5 text-sm font-medium text-white"
        >
          새 요청
        </Link>
      </div>

      {isLoading && <p className="text-sm text-text-secondary">불러오는 중...</p>}
      {error && <p className="text-sm text-status-critical">케이스 목록을 불러오지 못했습니다.</p>}

      {cases && cases.length === 0 && (
        <p className="text-sm text-text-secondary">아직 생성된 케이스가 없습니다.</p>
      )}

      {cases && cases.length > 0 && (
        <ul className="flex flex-col divide-y divide-border-subtle rounded-md border border-border-subtle">
          {cases.map((c) => (
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
    </div>
  );
}
