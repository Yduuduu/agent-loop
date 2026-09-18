import { beforeEach, describe, expect, it, vi } from "vitest";

import { MockEventSource, mockEventSourceConstructor } from "@/test-utils/mock-event-source";

import { connectKbDocumentStream } from "./kb-sse-client";

beforeEach(() => {
  MockEventSource.reset();
});

describe("connectKbDocumentStream", () => {
  it("dispatches chunking/embedding/indexed in order and closes on indexed", () => {
    const events: string[] = [];
    connectKbDocumentStream(
      "doc-1",
      {
        onChunking: () => events.push("chunking"),
        onEmbedding: () => events.push("embedding"),
        onIndexed: () => events.push("indexed"),
      },
      { EventSourceImpl: mockEventSourceConstructor },
    );

    const source = MockEventSource.last();
    source.emit("chunking", { doc_id: "doc-1", progress_pct: 25 });
    source.emit("embedding", { doc_id: "doc-1", progress_pct: 60, chunk_count: 2 });
    source.emit("indexed", { doc_id: "doc-1", progress_pct: 100, chunk_count: 2 });

    expect(events).toEqual(["chunking", "embedding", "indexed"]);
    expect(source.closed).toBe(true);
  });

  it("routes failed to onFailed and closes the stream", () => {
    const onFailed = vi.fn();
    const onIndexed = vi.fn();
    connectKbDocumentStream(
      "doc-2",
      { onFailed, onIndexed },
      { EventSourceImpl: mockEventSourceConstructor },
    );

    const source = MockEventSource.last();
    source.emit("failed", { doc_id: "doc-2", message: "PDF에서 추출할 텍스트가 없습니다" });

    expect(onFailed).toHaveBeenCalledWith({
      doc_id: "doc-2",
      message: "PDF에서 추출할 텍스트가 없습니다",
    });
    expect(onIndexed).not.toHaveBeenCalled();
    expect(source.closed).toBe(true);
  });

  it("does not close the stream on non-terminal progress events", () => {
    connectKbDocumentStream("doc-3", {}, { EventSourceImpl: mockEventSourceConstructor });
    const source = MockEventSource.last();

    source.emit("chunking", { doc_id: "doc-3" });
    expect(source.closed).toBe(false);

    source.emit("embedding", { doc_id: "doc-3" });
    expect(source.closed).toBe(false);
  });

  it("returns a cleanup function that closes the connection", () => {
    const disconnect = connectKbDocumentStream(
      "doc-4",
      {},
      { EventSourceImpl: mockEventSourceConstructor },
    );
    const source = MockEventSource.last();

    expect(source.closed).toBe(false);
    disconnect();
    expect(source.closed).toBe(true);
  });
});
