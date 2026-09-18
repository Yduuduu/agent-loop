import type { LiveUploadState } from "@/hooks/use-kb-upload-tracker";

const STAGE_LABELS: Record<string, string> = {
  uploaded: "업로드됨",
  chunking: "문서 분할 중...",
  embedding: "임베딩 생성 중...",
  indexed: "색인 완료",
  failed: "실패",
};

export function UploadProgress({
  filename,
  stage,
  progressPct,
  chunkCount,
  errorMessage,
}: LiveUploadState) {
  const barClass =
    stage === "failed"
      ? "bg-status-critical"
      : stage === "indexed"
        ? "bg-status-good"
        : "bg-status-progress";

  return (
    <div
      className="rounded-md border border-border-subtle p-3 text-sm"
      data-testid="upload-progress"
      data-stage={stage}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-medium">{filename}</span>
        <span className="shrink-0 text-text-secondary">{STAGE_LABELS[stage] ?? stage}</span>
      </div>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-surface-2">
        <div
          className={`h-full transition-[width] duration-300 ${barClass}`}
          style={{ width: `${progressPct}%` }}
          role="progressbar"
          aria-valuenow={progressPct}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
      {stage === "indexed" && chunkCount != null && (
        <p className="mt-1 text-text-secondary">{chunkCount}개 청크 색인됨</p>
      )}
      {errorMessage && <p className="mt-1 text-status-critical">{errorMessage}</p>}
    </div>
  );
}
