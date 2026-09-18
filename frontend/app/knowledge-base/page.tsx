"use client";

import { AppShell } from "@/components/app-shell";
import { DropZone } from "@/components/kb-upload/drop-zone";
import { UploadProgress } from "@/components/kb-upload/upload-progress";
import { useKbDocuments, useUploadKbDocument } from "@/hooks/use-kb-documents";
import { useKbUploadTracker } from "@/hooks/use-kb-upload-tracker";

const STATUS_LABELS: Record<string, string> = {
  uploaded: "업로드됨",
  chunking: "분할 중",
  embedding: "임베딩 중",
  indexed: "색인 완료",
  failed: "실패",
};

export default function KnowledgeBasePage() {
  const { data: documents, isLoading, error } = useKbDocuments();
  const upload = useUploadKbDocument();
  const { uploads, track } = useKbUploadTracker();

  const handleFilesAccepted = async (files: File[]) => {
    for (const file of files) {
      try {
        const result = await upload.mutateAsync(file);
        track(result.doc_id, file.name);
      } catch {
        // useUploadKbDocument의 isError로 별도 표시됨
      }
    }
  };

  return (
    <AppShell
      title="지식베이스 관리"
      subtitle="환불 정책 PDF를 업로드하면 자동으로 청킹·임베딩되어 검색에 반영됩니다."
    >
      <div className="flex w-full max-w-2xl flex-col gap-8">
      <DropZone onFilesAccepted={handleFilesAccepted} />

      {upload.isError && (
        <p className="text-sm text-status-critical">
          업로드에 실패했습니다: {String(upload.error)}
        </p>
      )}

      {Object.keys(uploads).length > 0 && (
        <section className="flex flex-col gap-2">
          {Object.entries(uploads).map(([docId, state]) => (
            <UploadProgress key={docId} {...state} />
          ))}
        </section>
      )}

      <section>
        <h2 className="mb-3 text-sm font-medium text-text-secondary">문서 목록</h2>

        {isLoading && <p className="text-sm text-text-secondary">불러오는 중...</p>}
        {error && <p className="text-sm text-status-critical">문서 목록을 불러오지 못했습니다.</p>}
        {documents && documents.length === 0 && (
          <p className="text-sm text-text-secondary">아직 업로드된 문서가 없습니다.</p>
        )}

        {documents && documents.length > 0 && (
          <ul className="flex flex-col divide-y divide-border-subtle rounded-md border border-border-subtle">
            {documents.map((doc) => (
              <li
                key={doc.doc_id}
                className="flex items-center justify-between gap-4 px-4 py-3 text-sm"
              >
                <span className="truncate">{doc.filename}</span>
                <div className="flex shrink-0 items-center gap-3 text-text-secondary">
                  <span>{STATUS_LABELS[doc.status] ?? doc.status}</span>
                  <span>{doc.chunk_count}청크</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
      </div>
    </AppShell>
  );
}
