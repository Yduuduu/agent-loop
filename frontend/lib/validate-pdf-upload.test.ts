import { describe, expect, it } from "vitest";

import { MAX_UPLOAD_BYTES, validatePdfFiles } from "./validate-pdf-upload";

function makeFile(name: string, sizeBytes: number, type = "application/pdf"): File {
  const blob = new Blob([new Uint8Array(sizeBytes)], { type });
  return new File([blob], name, { type });
}

describe("validatePdfFiles", () => {
  it("accepts a well-formed PDF", () => {
    const file = makeFile("policy.pdf", 1024);
    const result = validatePdfFiles([file]);
    expect(result.valid).toEqual([file]);
    expect(result.errors).toEqual([]);
  });

  it("rejects non-PDF files by extension", () => {
    const file = makeFile("notes.txt", 1024, "text/plain");
    const result = validatePdfFiles([file]);
    expect(result.valid).toEqual([]);
    expect(result.errors[0]).toContain("PDF 파일만");
  });

  it("rejects empty files", () => {
    const file = makeFile("empty.pdf", 0);
    const result = validatePdfFiles([file]);
    expect(result.valid).toEqual([]);
    expect(result.errors[0]).toContain("빈 파일");
  });

  it("rejects files over the size limit", () => {
    const file = makeFile("huge.pdf", MAX_UPLOAD_BYTES + 1);
    const result = validatePdfFiles([file]);
    expect(result.valid).toEqual([]);
    expect(result.errors[0]).toContain("너무 큽니다");
  });

  it("partitions a mixed batch into valid files and per-file errors", () => {
    const good = makeFile("good.pdf", 1024);
    const bad = makeFile("bad.txt", 1024, "text/plain");
    const result = validatePdfFiles([good, bad]);
    expect(result.valid).toEqual([good]);
    expect(result.errors).toHaveLength(1);
  });
});
