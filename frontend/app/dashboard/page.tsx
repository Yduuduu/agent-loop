"use client";

import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { useRefundCases } from "@/hooks/use-refund-cases";
import { formatElapsed } from "@/lib/format-elapsed";
import { sortByAwaitingSince } from "@/lib/sort-queue";
import type { RefundCaseStatus } from "@/lib/types";

const STATUS_LABELS: Record<string, string> = {
  pending: "대기",
  in_progress: "처리 중",
  awaiting_human: "사람 검토 대기",
  completed: "완료",
  failed: "실패",
};

const STATUS_DOT: Record<string, string> = {
  pending: "bg-status-pending",
  in_progress: "bg-status-progress",
  awaiting_human: "bg-accent",
  completed: "bg-status-good",
  failed: "bg-status-critical",
};

function StatTile({ label, value, tone }: { label: string; value: number; tone?: "accent" | "critical" }) {
  return (
    <div className="flex flex-1 flex-col gap-2 border border-border-subtle bg-surface-3 px-5 py-4">
      <span className="text-sm text-text-secondary">{label}</span>
      <span
        className={`font-mono text-3xl leading-none tabular-nums ${
          tone === "accent" ? "text-accent" : tone === "critical" ? "text-status-critical" : "text-foreground"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

export default function DashboardPage() {
  const { data: allCases, isLoading, error } = useRefundCases();
  const { data: queueCases } = useRefundCases("awaiting_human");
  const queue = queueCases ? sortByAwaitingSince(queueCases) : [];

  const counts = (allCases ?? []).reduce<Record<RefundCaseStatus, number>>(
    (acc, c) => {
      acc[c.status] = (acc[c.status] ?? 0) + 1;
      return acc;
    },
    { pending: 0, in_progress: 0, awaiting_human: 0, completed: 0, failed: 0 },
  );

  return (
    <AppShell
      title="대시보드"
      subtitle="환불 요청 처리 현황"
      actions={
        <>
          <Link href="/knowledge-base" className="text-sm text-text-secondary hover:text-foreground">
            지식베이스
          </Link>
          <Link
            href="/refund-cases"
            className="rounded-sm bg-status-progress px-3.5 py-2 text-sm font-medium text-white hover:opacity-90"
          >
            새 요청
          </Link>
        </>
      }
    >
          <section className="flex gap-4">
            <StatTile label="사람 검토 대기" value={queue.length} tone="accent" />
            <StatTile label="전체 케이스" value={(allCases ?? []).length} />
            <StatTile label="처리 완료" value={counts.completed} />
            <StatTile label="실패" value={counts.failed} tone={counts.failed > 0 ? "critical" : undefined} />
          </section>

          {queue.length > 0 && (
            <section>
              <div className="mb-3 flex items-baseline justify-between">
                <h2 className="text-sm font-medium">사람 검토 대기 중</h2>
                <span className="text-xs text-text-secondary">{queue.length}건 · 오래 기다린 순</span>
              </div>
              <ul className="flex flex-col gap-2">
                {queue.map((c) => (
                  <li key={c.case_id}>
                    <Link
                      href={`/refund-cases/${c.case_id}`}
                      className="flex flex-col gap-1.5 border border-l-2 border-border-subtle border-l-accent bg-accent-soft/40 px-4 py-3.5 text-sm hover:bg-accent-soft/70"
                    >
                      <div className="flex items-center justify-between gap-4">
                        <span className="font-medium">{c.order_id}</span>
                        <div className="flex items-center gap-3 font-mono text-text-secondary">
                          {c.refund_amount != null && <span>${c.refund_amount.toFixed(2)}</span>}
                          {c.awaiting_human_since && <span>{formatElapsed(c.awaiting_human_since)}</span>}
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

          <section className="flex min-h-0 flex-1 flex-col">
            <h2 className="mb-3 text-sm font-medium">전체 케이스</h2>

            {isLoading && <p className="text-sm text-text-secondary">불러오는 중...</p>}
            {error && <p className="text-sm text-status-critical">케이스 목록을 불러오지 못했습니다.</p>}
            {allCases && allCases.length === 0 && (
              <p className="text-sm text-text-secondary">아직 생성된 케이스가 없습니다.</p>
            )}

            {allCases && allCases.length > 0 && (
              <div className="border border-border-subtle">
                <div className="flex items-center gap-4 border-b border-border-subtle bg-surface-2 px-4 py-2 text-xs text-text-secondary">
                  <span className="w-24 font-mono">케이스 ID</span>
                  <span className="flex-1">주문 번호</span>
                  <span className="w-32 text-right">상태</span>
                </div>
                <ul className="flex flex-col divide-y divide-border-subtle">
                  {allCases.map((c) => (
                    <li key={c.case_id}>
                      <Link
                        href={`/refund-cases/${c.case_id}`}
                        className="flex items-center gap-4 px-4 py-2.5 text-sm hover:bg-surface-2"
                      >
                        <span className="w-24 truncate font-mono text-xs text-text-secondary">
                          {c.case_id.slice(0, 8)}
                        </span>
                        <span className="flex-1">{c.order_id}</span>
                        <span className="flex w-32 items-center justify-end gap-2 text-text-secondary">
                          <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[c.status] ?? "bg-status-pending"}`} />
                          {STATUS_LABELS[c.status] ?? c.status}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
    </AppShell>
  );
}
