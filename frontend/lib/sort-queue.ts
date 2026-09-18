import type { RefundCaseStatusResponse } from "@/lib/types";

/** awaiting_human_since 오름차순(가장 오래 기다린 케이스가 먼저) 정렬 — FIFO 대기열. */
export function sortByAwaitingSince(cases: RefundCaseStatusResponse[]): RefundCaseStatusResponse[] {
  return [...cases].sort((a, b) => {
    if (!a.awaiting_human_since) return 1;
    if (!b.awaiting_human_since) return -1;
    return a.awaiting_human_since.localeCompare(b.awaiting_human_since);
  });
}
