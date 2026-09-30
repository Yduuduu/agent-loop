import type { PolicyItem } from "@/lib/types";

export function PolicyItemList({ items }: { items: PolicyItem[] }) {
  return (
    <ul className="flex flex-col gap-2">
      {items.map((item, i) => (
        <li key={`${item.title}-${i}`} className="rounded-sm border border-border-subtle p-3">
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
