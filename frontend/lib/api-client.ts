import type {
  RefundCaseStatus,
  RefundCaseStatusResponse,
  RefundRequestCreateResponse,
  RefundResumeRequest,
} from "@/lib/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

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

  const response = await fetch(`${API_BASE_URL}/api/refund-requests`, {
    method: "POST",
    body: form,
  });
  return parseOrThrow(response);
}

export async function getRefundRequest(caseId: string): Promise<RefundCaseStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/refund-requests/${caseId}`);
  return parseOrThrow(response);
}

export async function listRefundRequests(
  status?: RefundCaseStatus,
): Promise<RefundCaseStatusResponse[]> {
  const url = new URL(`${API_BASE_URL}/api/refund-requests`);
  if (status) url.searchParams.set("status", status);

  const response = await fetch(url);
  return parseOrThrow(response);
}

export async function resumeRefundRequest(
  caseId: string,
  payload: RefundResumeRequest,
): Promise<RefundRequestCreateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/refund-requests/${caseId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(response);
}

export function refundStreamUrl(caseId: string): string {
  return `${API_BASE_URL}/api/refund-requests/${caseId}/stream`;
}
