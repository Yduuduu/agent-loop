"use client";

import { PolicyItemList } from "@/components/kb/policy-item-list";
import { useKbPolicies } from "@/hooks/use-kb-documents";
import type { PolicyGroup } from "@/lib/types";

/** 백엔드가 분류 체계 순서로 정렬해 준 (대분류, 소분류) 그룹을 대분류 단위로 묶는다. */
function groupByProductCategory(groups: PolicyGroup[]): [string, PolicyGroup[]][] {
  const byCategory = new Map<string, PolicyGroup[]>();
  for (const group of groups) {
    const list = byCategory.get(group.product_category) ?? [];
    list.push(group);
    byCategory.set(group.product_category, list);
  }
  return Array.from(byCategory.entries());
}

export function PolicyDashboard() {
  const { data: groups, isLoading, error } = useKbPolicies();

  if (isLoading) {
    return <p className="text-sm text-text-secondary">정책을 불러오는 중...</p>;
  }
  if (error) {
    return <p className="text-sm text-status-critical">정책 목록을 불러오지 못했습니다.</p>;
  }
  if (!groups || groups.length === 0) {
    return (
      <p className="text-sm text-text-secondary">
        아직 요약된 정책이 없습니다. 문서 인덱싱이 끝나면 자동으로 채워집니다.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {groupByProductCategory(groups).map(([productCategory, typeGroups]) => (
        <section key={productCategory}>
          <h3 className="mb-3 text-sm font-semibold">{productCategory}</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {typeGroups.map((group) => (
              <div
                key={group.policy_type}
                className="rounded-md border border-border-subtle bg-surface-2 p-4"
              >
                <h4 className="mb-3 text-sm font-semibold text-accent">{group.policy_type}</h4>
                <PolicyItemList items={group.items} />
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
