import type { PolicyItem } from "@/lib/types";

export function PolicyItemList({
  items,
  showPolicyType = false,
}: {
  items: PolicyItem[];
  // 소분류로 묶이지 않은 목록(문서 상세 모달)에서만 항목별 소분류를 표시한다.
  showPolicyType?: boolean;
}) {
  return (
    <ul className="flex flex-col gap-2">
      {items.map((item, i) => (
        <li key={`${item.title}-${i}`} className="rounded-sm border border-border-subtle p-3">
          {showPolicyType && (
            <span className="mb-1 inline-block rounded-sm bg-accent-soft px-1.5 py-0.5 text-xs text-accent">
              {item.policy_type}
            </span>
          )}
          <p className="text-sm font-medium">{item.title}</p>
          <p className="mt-1 text-sm text-text-secondary">{item.summary}</p>
          <p className="mt-2 truncate text-xs text-text-secondary/80" title={item.source_excerpt}>
            근거: “{item.source_excerpt}”
          </p>
        </li>
      ))}
    </ul>
  );
}
