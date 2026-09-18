import { describe, expect, it } from "vitest";

import type { RefundCaseStatusResponse } from "./types";
import { sortByAwaitingSince } from "./sort-queue";

function makeCase(caseId: string, awaitingSince: string | null): RefundCaseStatusResponse {
  return {
    case_id: caseId,
    order_id: "ORD-1001",
    status: "awaiting_human",
    requires_human: true,
    decision: null,
    decision_reason: null,
    flagged_reason: null,
    refund_amount: null,
    awaiting_human_since: awaitingSince,
    created_at: "2026-09-18T00:00:00Z",
    updated_at: "2026-09-18T00:00:00Z",
  };
}

describe("sortByAwaitingSince", () => {
  it("orders the oldest-waiting case first (FIFO queue)", () => {
    const cases = [
      makeCase("newest", "2026-09-18T12:00:00Z"),
      makeCase("oldest", "2026-09-18T10:00:00Z"),
      makeCase("middle", "2026-09-18T11:00:00Z"),
    ];

    expect(sortByAwaitingSince(cases).map((c) => c.case_id)).toEqual([
      "oldest",
      "middle",
      "newest",
    ]);
  });

  it("pushes cases with no awaiting_human_since to the end", () => {
    const cases = [
      makeCase("no-timestamp", null),
      makeCase("has-timestamp", "2026-09-18T10:00:00Z"),
    ];

    expect(sortByAwaitingSince(cases).map((c) => c.case_id)).toEqual([
      "has-timestamp",
      "no-timestamp",
    ]);
  });

  it("does not mutate the input array", () => {
    const cases = [makeCase("a", "2026-09-18T12:00:00Z"), makeCase("b", "2026-09-18T10:00:00Z")];
    const original = [...cases];

    sortByAwaitingSince(cases);

    expect(cases).toEqual(original);
  });
});
