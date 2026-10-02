import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { KBDocumentResponse } from "@/lib/types";

import { useKbPolicies } from "./use-kb-documents";

const api = vi.hoisted(() => ({
  listKbDocuments: vi.fn(),
  listKbPolicies: vi.fn(),
}));

vi.mock("@/lib/api-client", () => api);

function makeDoc(policySummaryStatus: KBDocumentResponse["policy_summary_status"]) {
  return {
    doc_id: "doc-1",
    filename: "policy.pdf",
    product_category: "도서",
    status: "indexed",
    progress_pct: 100,
    chunk_count: 1,
    created_at: "2026-10-01T00:00:00",
    policy_summary_status: policySummaryStatus,
    policy_summary: null,
  } satisfies KBDocumentResponse;
}

describe("useKbPolicies", () => {
  it("refetches policies once a document's summary finishes after indexing", async () => {
    api.listKbDocuments.mockResolvedValue([makeDoc("summarizing")]);
    api.listKbPolicies.mockResolvedValue([]);

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useKbPolicies(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const callsBefore = api.listKbPolicies.mock.calls.length;

    // 문서 목록 폴링에서 요약 완료가 관측되면 정책 목록도 다시 불러와야 한다.
    api.listKbDocuments.mockResolvedValue([makeDoc("done")]);
    await act(() => queryClient.invalidateQueries({ queryKey: ["kb-documents"] }));

    await waitFor(() => expect(api.listKbPolicies.mock.calls.length).toBeGreaterThan(callsBefore));
  });
});
