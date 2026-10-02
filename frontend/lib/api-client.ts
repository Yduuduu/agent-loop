import type {
  KBDocumentCreateResponse,
  KBDocumentResponse,
  PolicyCategoryResponse,
  PolicyGroup,
  RefundCaseStatus,
  RefundCaseStatusResponse,
  RefundRequestCreateResponse,
  RefundResumeRequest,
} from "@/lib/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

// 백엔드는 프론트와 다른 origin(Phase 6.2: HTTP Basic 인증)이라, fetch 기본
// credentials 모드("same-origin")로는 브라우저가 캐시해둔 인증 정보를 담아
// 보내지 않는다 — 모든 요청에 명시적으로 "include"를 지정해야 한다.
//
// X-Requested-With 헤더는 CSRF 방지용이다(백엔드 app/api/deps.py의
// require_admin_auth 참고) — 일반 HTML <form> 제출로는 이 커스텀 헤더를
// 붙일 수 없으므로, 상태를 바꾸는 요청(POST/DELETE 등)에 이 헤더가 없으면
// 백엔드가 거부한다. 모든 요청에 붙여도 안전하므로 통일한다.
function apiFetch(input: string | URL, init: RequestInit = {}): Promise<Response> {
  return fetch(input, {
    ...init,
    credentials: "include",
    headers: { ...init.headers, "X-Requested-With": "XMLHttpRequest" },
  });
}

async function parseOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }
  return response.json() as Promise<T>;
}

export async function createRefundRequest(input: {
  orderId: string;
  message: string;
  images?: File[];
}): Promise<RefundRequestCreateResponse> {
  const form = new FormData();
  form.set("order_id", input.orderId);
  form.set("message", input.message);
  for (const image of input.images ?? []) {
    form.append("images", image);
  }

  const response = await apiFetch(`${API_BASE_URL}/api/refund-requests`, {
    method: "POST",
    body: form,
  });
  return parseOrThrow(response);
}

export async function getRefundRequest(caseId: string): Promise<RefundCaseStatusResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/refund-requests/${caseId}`);
  return parseOrThrow(response);
}

export async function listRefundRequests(
  status?: RefundCaseStatus,
): Promise<RefundCaseStatusResponse[]> {
  const url = new URL(`${API_BASE_URL}/api/refund-requests`);
  if (status) url.searchParams.set("status", status);

  const response = await apiFetch(url);
  return parseOrThrow(response);
}

export async function resumeRefundRequest(
  caseId: string,
  payload: RefundResumeRequest,
): Promise<RefundRequestCreateResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/refund-requests/${caseId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(response);
}

export function refundStreamUrl(caseId: string): string {
  return `${API_BASE_URL}/api/refund-requests/${caseId}/stream`;
}

export async function uploadKbDocument({
  file,
  productCategory,
}: {
  file: File;
  productCategory: string;
}): Promise<KBDocumentCreateResponse> {
  const form = new FormData();
  form.set("file", file);
  form.set("product_category", productCategory);

  const response = await apiFetch(`${API_BASE_URL}/api/knowledge-base/documents`, {
    method: "POST",
    body: form,
  });
  return parseOrThrow(response);
}

export async function listKbDocuments(): Promise<KBDocumentResponse[]> {
  const response = await apiFetch(`${API_BASE_URL}/api/knowledge-base/documents`);
  return parseOrThrow(response);
}

export async function getKbDocument(docId: string): Promise<KBDocumentResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/knowledge-base/documents/${docId}`);
  return parseOrThrow(response);
}

export function kbDocumentStreamUrl(docId: string): string {
  return `${API_BASE_URL}/api/knowledge-base/documents/${docId}/stream`;
}

export function kbDocumentFileUrl(docId: string): string {
  return `${API_BASE_URL}/api/knowledge-base/documents/${docId}/file`;
}

export async function deleteKbDocument(docId: string): Promise<void> {
  const response = await apiFetch(`${API_BASE_URL}/api/knowledge-base/documents/${docId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }
}

export async function listKbCategories(): Promise<PolicyCategoryResponse[]> {
  const response = await apiFetch(`${API_BASE_URL}/api/knowledge-base/categories`);
  return parseOrThrow(response);
}

export async function listKbPolicies(): Promise<PolicyGroup[]> {
  const response = await apiFetch(`${API_BASE_URL}/api/knowledge-base/policies`);
  return parseOrThrow(response);
}
