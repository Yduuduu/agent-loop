"use client";

import { useRef, useState } from "react";

import { validatePdfFiles } from "@/lib/validate-pdf-upload";

interface DropZoneProps {
  onFilesAccepted: (files: File[]) => void;
  disabled?: boolean;
}

export function DropZone({ onFilesAccepted, disabled }: DropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

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
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (!disabled && (e.key === "Enter" || e.key === " ")) inputRef.current?.click();
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          if (!disabled) handleFiles(e.dataTransfer.files);
        }}
        data-testid="kb-drop-zone"
        className={`flex cursor-pointer flex-col items-center justify-center gap-1 rounded-md border-2 border-dashed p-8 text-center text-sm transition-colors ${
          isDragging ? "border-status-progress bg-status-progress/5" : "border-border-subtle"
        } ${disabled ? "pointer-events-none opacity-50" : ""}`}
      >
        <p className="font-medium">PDF 파일을 드래그하거나 클릭해서 업로드</p>
        <p className="text-text-secondary">최대 20MB, PDF 형식만 지원</p>
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

      {errors.length > 0 && (
        <ul className="mt-2 flex flex-col gap-0.5 text-sm text-status-critical">
          {errors.map((err) => (
            <li key={err}>{err}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
