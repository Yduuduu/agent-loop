"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { connectKbDocumentStream } from "@/lib/kb-sse-client";
import type { EventSourceConstructor } from "@/lib/sse-client";
import type { KBDocumentStatus } from "@/lib/types";

export interface LiveUploadState {
  filename: string;
  stage: KBDocumentStatus;
  progressPct: number;
  chunkCount?: number;
  errorMessage?: string;
}

/** 업로드 직후 문서별 SSE 진행 상황을 추적한다. 완료/실패 시 문서 목록
 * 쿼리를 무효화해 정적 목록도 최신 상태로 맞춘다. */
export function useKbUploadTracker(eventSourceImpl?: EventSourceConstructor) {
  const queryClient = useQueryClient();
  const [uploads, setUploads] = useState<Record<string, LiveUploadState>>({});

  const update = useCallback((docId: string, patch: Partial<LiveUploadState>) => {
    setUploads((prev) => ({ ...prev, [docId]: { ...prev[docId], ...patch } as LiveUploadState }));
  }, []);

  const track = useCallback(
    (docId: string, filename: string) => {
      setUploads((prev) => ({ ...prev, [docId]: { filename, stage: "uploaded", progressPct: 0 } }));

      connectKbDocumentStream(
        docId,
        {
          onChunking: (d) =>
            update(docId, { stage: "chunking", progressPct: d.progress_pct ?? 25 }),
          onEmbedding: (d) =>
            update(docId, {
              stage: "embedding",
              progressPct: d.progress_pct ?? 60,
              chunkCount: d.chunk_count,
            }),
          onIndexed: (d) => {
            update(docId, { stage: "indexed", progressPct: 100, chunkCount: d.chunk_count });
            void queryClient.invalidateQueries({ queryKey: ["kb-documents"] });
          },
          onFailed: (d) => {
            update(docId, { stage: "failed", errorMessage: d.message });
            void queryClient.invalidateQueries({ queryKey: ["kb-documents"] });
          },
        },
        eventSourceImpl ? { EventSourceImpl: eventSourceImpl } : undefined,
      );
    },
    [queryClient, update, eventSourceImpl],
  );

  return { uploads, track };
}
