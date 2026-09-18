import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { MockEventSource, mockEventSourceConstructor } from "@/test-utils/mock-event-source";

import { useKbUploadTracker } from "./use-kb-upload-tracker";

beforeEach(() => {
  MockEventSource.reset();
});

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("useKbUploadTracker", () => {
  it("tracks a document through chunking -> embedding -> indexed", () => {
    const { result } = renderHook(() => useKbUploadTracker(mockEventSourceConstructor), {
      wrapper,
    });

    act(() => result.current.track("doc-1", "policy.pdf"));
    expect(result.current.uploads["doc-1"]).toEqual({
      filename: "policy.pdf",
      stage: "uploaded",
      progressPct: 0,
    });

    const source = MockEventSource.last();

    act(() => source.emit("chunking", { doc_id: "doc-1", progress_pct: 25 }));
    expect(result.current.uploads["doc-1"].stage).toBe("chunking");
    expect(result.current.uploads["doc-1"].progressPct).toBe(25);

    act(() => source.emit("embedding", { doc_id: "doc-1", progress_pct: 60, chunk_count: 3 }));
    expect(result.current.uploads["doc-1"].stage).toBe("embedding");
    expect(result.current.uploads["doc-1"].chunkCount).toBe(3);

    act(() => source.emit("indexed", { doc_id: "doc-1", progress_pct: 100, chunk_count: 3 }));
    expect(result.current.uploads["doc-1"]).toEqual({
      filename: "policy.pdf",
      stage: "indexed",
      progressPct: 100,
      chunkCount: 3,
    });
  });

  it("records a failure message and stage without touching other tracked uploads", () => {
    const { result } = renderHook(() => useKbUploadTracker(mockEventSourceConstructor), {
      wrapper,
    });

    act(() => result.current.track("doc-1", "good.pdf"));
    const firstSource = MockEventSource.last();

    act(() => result.current.track("doc-2", "bad.pdf"));
    const secondSource = MockEventSource.last();

    act(() =>
      secondSource.emit("failed", { doc_id: "doc-2", message: "추출할 텍스트가 없습니다" }),
    );

    expect(result.current.uploads["doc-2"].stage).toBe("failed");
    expect(result.current.uploads["doc-2"].errorMessage).toBe("추출할 텍스트가 없습니다");
    expect(result.current.uploads["doc-1"].stage).toBe("uploaded");

    act(() => firstSource.emit("indexed", { doc_id: "doc-1", progress_pct: 100, chunk_count: 1 }));
    expect(result.current.uploads["doc-1"].stage).toBe("indexed");
    expect(result.current.uploads["doc-2"].stage).toBe("failed");
  });
});
