// 백엔드 app/api/routes/knowledge_base.py의 MAX_UPLOAD_BYTES/PDF 검증과 동일한 기준
// — 서버 검증을 대신하지 않고, 명백히 잘못된 업로드를 즉시 걸러내 왕복을 줄인다.
export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

export interface PdfValidationResult {
  valid: File[];
  errors: string[];
}

export function validatePdfFiles(files: File[]): PdfValidationResult {
  const valid: File[] = [];
  const errors: string[] = [];

  for (const file of files) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      errors.push(`${file.name}: PDF 파일만 업로드할 수 있습니다.`);
      continue;
    }
    if (file.size === 0) {
      errors.push(`${file.name}: 빈 파일입니다.`);
      continue;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      errors.push(`${file.name}: 파일이 너무 큽니다 (최대 20MB).`);
      continue;
    }
    valid.push(file);
  }

  return { valid, errors };
}
