"use client";

import { PolicyItemList } from "@/components/kb/policy-item-list";
import { useKbPolicies } from "@/hooks/use-kb-documents";

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
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {groups.map((group) => (
        <div key={group.category} className="rounded-md border border-border-subtle bg-surface-2 p-4">
          <h3 className="mb-3 text-sm font-semibold text-accent">{group.category}</h3>
          <PolicyItemList items={group.items} />
        </div>
      ))}
    </div>
  );
}
