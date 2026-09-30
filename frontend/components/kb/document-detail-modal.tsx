"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/kb/confirm-dialog";
import { PolicyItemList } from "@/components/kb/policy-item-list";
import { useDeleteKbDocument } from "@/hooks/use-kb-documents";
import { kbDocumentFileUrl } from "@/lib/api-client";
import type { KBDocumentResponse } from "@/lib/types";

const STATUS_LABELS: Record<string, string> = {
  uploaded: "업로드됨",
  chunking: "분할 중",
  embedding: "임베딩 중",
  indexed: "색인 완료",
  failed: "실패",
};

const POLICY_SUMMARY_STATUS_LABELS: Record<string, string> = {
  pending: "정책 요약 대기 중",
  summarizing: "정책 요약 생성 중...",
  done: "정책 요약 완료",
  failed: "정책 요약 실패",
};

export function DocumentDetailModal({
  doc,
  onClose,
  onDeleted,
}: {
  doc: KBDocumentResponse;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const deleteDoc = useDeleteKbDocument();

  const handleDelete = () => {
    deleteDoc.mutate(doc.doc_id, {
      onSuccess: () => {
        setConfirmingDelete(false);
        onDeleted();
      },
    });
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="flex max-h-[80vh] w-full max-w-lg flex-col rounded-md border border-border-subtle bg-surface-3 p-5 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold">{doc.filename}</h2>
            <p className="mt-1 text-xs text-text-secondary">
              {STATUS_LABELS[doc.status] ?? doc.status} · {doc.chunk_count}청크 ·{" "}
              {new Date(doc.created_at).toLocaleString()}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            className="shrink-0 text-text-secondary hover:text-foreground"
          >
            ✕
          </button>
        </div>

        <div className="mt-4 flex gap-2">
          <a
            href={kbDocumentFileUrl(doc.doc_id)}
            target="_blank"
            rel="noreferrer"
            className="rounded-sm border border-border-subtle px-3 py-1.5 text-sm hover:bg-surface-2"
          >
            원문 보기
          </a>
          <button
            type="button"
            onClick={() => setConfirmingDelete(true)}
            className="rounded-sm border border-status-critical px-3 py-1.5 text-sm text-status-critical hover:bg-status-critical/10"
          >
            삭제
          </button>
        </div>

        {deleteDoc.isError && (
          <p className="mt-2 text-sm text-status-critical">
            삭제에 실패했습니다: {String(deleteDoc.error)}
          </p>
        )}

        <div className="mt-5 min-h-0 flex-1 overflow-y-auto">
          <h3 className="mb-2 text-xs font-medium text-text-secondary">
            {POLICY_SUMMARY_STATUS_LABELS[doc.policy_summary_status] ?? doc.policy_summary_status}
          </h3>
          {doc.policy_summary && doc.policy_summary.length > 0 ? (
            <PolicyItemList items={doc.policy_summary} />
          ) : (
            <p className="text-sm text-text-secondary">
              {doc.policy_summary_status === "done"
                ? "추출된 정책 항목이 없습니다."
                : "정책 요약이 아직 준비되지 않았습니다."}
            </p>
          )}
        </div>
      </div>

      {confirmingDelete && (
        <ConfirmDialog
          title="문서를 삭제할까요?"
          description={`"${doc.filename}" 문서와 관련 검색 색인이 영구적으로 삭제됩니다. 되돌릴 수 없습니다.`}
          confirmLabel="삭제"
          destructive
          isConfirming={deleteDoc.isPending}
          onConfirm={handleDelete}
          onCancel={() => setConfirmingDelete(false)}
        />
      )}
    </div>
  );
}
