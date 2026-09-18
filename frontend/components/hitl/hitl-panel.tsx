"use client";

import { useState } from "react";

import { useResumeRefundRequest } from "@/hooks/use-refund-cases";
import type { RefundResumeRequest } from "@/lib/types";

interface HitlPanelProps {
  caseId: string;
  flaggedReason: string | null;
  refundAmount: number | null;
  /** resume 성공 시 호출 — 호출자가 SSE 스트림을 재연결하는 데 쓴다. */
  onResumed: () => void;
}

type ConfirmingAction = "reject" | "takeover" | null;

// MVP 단순화: 실제 다중 관리자 인증/동시 처리 충돌 방지는 다루지 않는다
// (last-write-wins — 두 관리자가 동시에 열어도 마지막 resume 호출이 이긴다).
export function HitlPanel({ caseId, flaggedReason, refundAmount, onResumed }: HitlPanelProps) {
  const resume = useResumeRefundRequest(caseId);
  const [adminNote, setAdminNote] = useState("");
  const [adminMessage, setAdminMessage] = useState("");
  const [confirming, setConfirming] = useState<ConfirmingAction>(null);

  const runResume = async (payload: RefundResumeRequest) => {
    await resume.mutateAsync(payload);
    onResumed();
  };

  return (
    <div
      className="rounded-md border border-status-progress/30 bg-status-progress/5 p-4"
      data-testid="hitl-panel"
    >
      <h2 className="text-sm font-semibold text-foreground">사람 검토 필요</h2>

      {refundAmount != null && (
        <p className="mt-1 text-sm text-text-secondary">환불 금액: ${refundAmount.toFixed(2)}</p>
      )}
      {flaggedReason && <p className="mt-1 text-sm text-text-secondary">{flaggedReason}</p>}

      <label className="mt-4 flex flex-col gap-1 text-sm">
        <span className="font-medium">내부 메모 (선택, 승인/거절 사유로 기록됨)</span>
        <textarea
          className="min-h-16 rounded-md border border-border-subtle bg-transparent px-3 py-2 text-sm"
          value={adminNote}
          onChange={(e) => setAdminNote(e.target.value)}
          disabled={resume.isPending}
        />
      </label>

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => runResume({ action: "approve", admin_note: adminNote || null })}
          disabled={resume.isPending}
          className="rounded-md bg-status-good px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          승인
        </button>
        <button
          type="button"
          onClick={() => setConfirming("reject")}
          disabled={resume.isPending}
          className="rounded-md bg-status-critical px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          거절
        </button>
      </div>

      {confirming === "reject" && (
        <ConfirmBox
          message="정말 이 환불 요청을 거절하시겠습니까? 되돌릴 수 없습니다."
          confirmLabel="거절 확정"
          onConfirm={() => {
            setConfirming(null);
            void runResume({ action: "reject", admin_note: adminNote || null });
          }}
          onCancel={() => setConfirming(null)}
        />
      )}

      <div className="mt-4 border-t border-border-subtle pt-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">직접 개입 (자유 텍스트 — 고객에게 전달될 처리 결과)</span>
          <textarea
            className="min-h-20 rounded-md border border-border-subtle bg-transparent px-3 py-2 text-sm"
            value={adminMessage}
            onChange={(e) => setAdminMessage(e.target.value)}
            disabled={resume.isPending}
            placeholder="예: 고객과 직접 협의해 부분 환불로 처리했습니다."
          />
        </label>
        <button
          type="button"
          onClick={() => setConfirming("takeover")}
          disabled={!adminMessage.trim() || resume.isPending}
          className="mt-2 rounded-md border border-status-progress px-4 py-2 text-sm font-medium text-status-progress disabled:opacity-50"
        >
          직접 개입으로 처리
        </button>
      </div>

      {confirming === "takeover" && (
        <ConfirmBox
          message="이 메시지로 케이스를 직접 종결 처리합니다. 그래프가 다시 추론하지 않고 이 내용이 바로 최종 사유가 됩니다. 되돌릴 수 없습니다."
          confirmLabel="직접 개입 확정"
          onConfirm={() => {
            setConfirming(null);
            void runResume({ action: "takeover", admin_message: adminMessage });
          }}
          onCancel={() => setConfirming(null)}
        />
      )}

      {resume.isError && (
        <p className="mt-3 text-sm text-status-critical">
          처리에 실패했습니다: {String(resume.error)}
        </p>
      )}
    </div>
  );
}

function ConfirmBox({
  message,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="mt-3 rounded-md border border-status-critical/40 bg-status-critical/5 p-3 text-sm">
      <p className="text-foreground">{message}</p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={onConfirm}
          className="rounded-md bg-status-critical px-3 py-1.5 text-xs font-medium text-white"
        >
          {confirmLabel}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-border-subtle px-3 py-1.5 text-xs font-medium"
        >
          취소
        </button>
      </div>
    </div>
  );
}
