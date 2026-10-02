// 백엔드 app/api/schemas/{sse_events,refund}.py 와 1:1로 대응하는 고정 계약.
// 필드명을 바꾸면 백엔드도 함께 갱신해야 한다.

export type SSEEventType =
  "node_start" | "node_end" | "tool_call" | "decision" | "error" | "awaiting_human";

export interface NodeStartData {
  case_id: string;
  node: string;
}

export interface NodeEndData {
  case_id: string;
  node: string;
  summary: string;
}

export interface ToolCallData {
  case_id: string;
  node: string;
  summary: string;
}

export interface DecisionData {
  case_id: string;
  decision: "approve" | "reject" | "needs_human" | "resolved" | null;
  reason: string | null;
  requires_human: boolean;
}

export interface AwaitingHumanData {
  case_id: string;
  reason: string | null;
  suggested_decision: string | null;
}

export interface ErrorData {
  case_id: string;
  message: string;
}

export type RefundCaseStatus =
  "pending" | "in_progress" | "awaiting_human" | "completed" | "failed";

export interface RefundCaseStatusResponse {
  case_id: string;
  order_id: string;
  status: RefundCaseStatus;
  requires_human: boolean;
  decision: "approve" | "reject" | "needs_human" | "resolved" | null;
  decision_reason: string | null;
  flagged_reason: string | null;
  refund_amount: number | null;
  awaiting_human_since: string | null;
  created_at: string;
  updated_at: string;
}

export interface RefundRequestCreateResponse {
  case_id: string;
}

export type ResumeAction = "approve" | "reject" | "takeover";

export interface RefundResumeRequest {
  action: ResumeAction;
  admin_note?: string | null;
  admin_message?: string | null;
}

// --- 지식베이스(Phase 6) — 백엔드 app/api/schemas/{kb_events,knowledge_base}.py ---

export type KBEventType = "uploaded" | "chunking" | "embedding" | "indexed" | "failed";

export interface KBProgressData {
  doc_id: string;
  progress_pct?: number;
  chunk_count?: number;
}

export interface KBFailedData {
  doc_id: string;
  message: string;
}

export type KBDocumentStatus = "uploaded" | "chunking" | "embedding" | "indexed" | "failed";

// 정책 분류 체계(대분류 → 소분류)는 백엔드 app/core/policy_categories.py가 단일 소스다.
// 프론트는 GET /api/knowledge-base/categories로 받아 쓰므로 라벨을 하드코딩하지 않는다.
export interface PolicyCategoryResponse {
  product_category: string;
  policy_types: string[];
}

export interface PolicyItem {
  // 소분류 라벨. 분류 도입 이전 요약은 구버전 라벨(환불기한 등)이 그대로 올 수 있다.
  policy_type: string;
  title: string;
  summary: string;
  source_excerpt: string;
}

export type PolicySummaryStatus = "pending" | "summarizing" | "done" | "failed";

export interface KBDocumentResponse {
  doc_id: string;
  filename: string;
  // 대분류 라벨. null이면 미분류.
  product_category: string | null;
  status: KBDocumentStatus;
  progress_pct: number;
  chunk_count: number;
  created_at: string;
  policy_summary_status: PolicySummaryStatus;
  policy_summary: PolicyItem[] | null;
}

export interface KBDocumentCreateResponse {
  doc_id: string;
}

export interface PolicyGroup {
  // 미분류 문서는 "미분류"로 온다.
  product_category: string;
  policy_type: string;
  items: PolicyItem[];
}
