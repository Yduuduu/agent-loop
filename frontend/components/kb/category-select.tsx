"use client";

import { useKbCategories } from "@/hooks/use-kb-documents";

/** 업로드할 정책서의 대분류 선택. 선택지는 백엔드 분류 체계를 그대로 쓴다. */
export function CategorySelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const { data: categories, isLoading, error } = useKbCategories();

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor="kb-product-category" className="text-sm font-medium">
        정책 대분류
      </label>
      <select
        id="kb-product-category"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={isLoading || Boolean(error)}
        className="rounded-md border border-border-subtle bg-surface-3 px-3 py-2 text-sm disabled:opacity-60"
      >
        <option value="">대분류를 선택하세요</option>
        {categories?.map((c) => (
          <option key={c.product_category} value={c.product_category}>
            {c.product_category}
          </option>
        ))}
      </select>
      {value && categories && (
        <p className="text-xs text-text-secondary">
          소분류: {categories.find((c) => c.product_category === value)?.policy_types.join(" · ")}
        </p>
      )}
      {error && <p className="text-sm text-status-critical">분류 목록을 불러오지 못했습니다.</p>}
    </div>
  );
}
