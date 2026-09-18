// 백엔드 노드 이름 → 사용자 친화 라벨. 백엔드 STATIC_NEXT/TERMINAL_NODES와
// 이름이 일치해야 한다(app/api/refund_runner.py 참고).

const IN_PROGRESS_LABELS: Record<string, string> = {
  order_lookup: "주문 내역 조회 중...",
  damage_assessment: "파손 여부 판정 중...",
  policy_rag_search: "관련 정책 검색 중...",
  decision: "최종 판정 산출 중...",
  finalize: "판정 확정 중...",
  flag_for_human: "사람 검토 대기 확인 중...",
};

const DONE_LABELS: Record<string, string> = {
  order_lookup: "주문 내역 조회 완료",
  damage_assessment: "파손 여부 판정 완료",
  policy_rag_search: "관련 정책 검색 완료",
  decision: "최종 판정 완료",
  finalize: "판정 확정 완료",
  flag_for_human: "사람 검토로 전환됨",
};

export function labelForNode(node: string, done: boolean): string {
  const table = done ? DONE_LABELS : IN_PROGRESS_LABELS;
  return table[node] ?? node;
}
