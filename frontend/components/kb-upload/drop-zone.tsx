"use client";

import { useRef, useState } from "react";

import { validatePdfFiles } from "@/lib/validate-pdf-upload";

interface DropZoneProps {
  onFilesAccepted: (files: File[]) => void;
  disabled?: boolean;
  // 비활성 상태에서 드롭/클릭을 시도했을 때 보여줄 안내 문구.
  disabledReason?: string;
}

export function DropZone({ onFilesAccepted, disabled, disabledReason }: DropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  // 비활성 상태에서 업로드를 시도했는지 — 안내 문구는 비활성인 동안에만 보여
  // 활성화(예: 대분류 선택) 이후에 낡은 안내가 남지 않는다.
  const [blockedAttempt, setBlockedAttempt] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const blockedMessage = disabledReason ?? "지금은 업로드할 수 없습니다.";
  const visibleErrors = disabled ? (blockedAttempt ? [blockedMessage] : []) : errors;

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const { valid, errors: validationErrors } = validatePdfFiles(Array.from(fileList));
    setErrors(validationErrors);
    if (valid.length > 0) onFilesAccepted(valid);
  };

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-disabled={disabled}
        onClick={() => (disabled ? setBlockedAttempt(true) : inputRef.current?.click())}
        onKeyDown={(e) => {
          if (e.key !== "Enter" && e.key !== " ") return;
          if (disabled) setBlockedAttempt(true);
          else inputRef.current?.click();
        }}
        // 비활성 상태여도 드래그 이벤트는 받아서 preventDefault 해야 한다 — 그러지 않으면
        // 드롭이 브라우저 기본 동작(파일 열기)으로 넘어가 아무 안내 없이 사라진다.
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          if (disabled) setBlockedAttempt(true);
          else handleFiles(e.dataTransfer.files);
        }}
        data-testid="kb-drop-zone"
        className={`flex flex-col items-center justify-center gap-1 rounded-md border-2 border-dashed p-8 text-center text-sm transition-colors ${
          isDragging
            ? disabled
              ? "border-status-critical bg-status-critical/5"
              : "border-status-progress bg-status-progress/5"
            : "border-border-subtle"
        } ${disabled ? "cursor-not-allowed text-text-secondary" : "cursor-pointer"}`}
      >
        <p className="font-medium">PDF 파일을 드래그하거나 클릭해서 업로드</p>
        <p className="text-text-secondary">
          {disabled && disabledReason ? disabledReason : "최대 20MB, PDF 형식만 지원"}
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        multiple
        className="hidden"
        disabled={disabled}
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = "";
        }}
        aria-label="PDF 파일 선택"
      />

      {visibleErrors.length > 0 && (
        <ul role="alert" className="mt-2 flex flex-col gap-0.5 text-sm text-status-critical">
          {visibleErrors.map((err) => (
            <li key={err}>{err}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
