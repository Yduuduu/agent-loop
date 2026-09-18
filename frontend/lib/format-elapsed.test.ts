import { describe, expect, it } from "vitest";

import { formatElapsed } from "./format-elapsed";

describe("formatElapsed", () => {
  const now = new Date("2026-09-18T12:00:00Z");

  it("treats a timezone-less backend timestamp (datetime.utcnow()) as UTC, not local time", () => {
    // 타임존 표기가 없어도 UTC로 해석해야 한다 — 로컬 시간대로 오해석하면
    // 실제 경과 시간과 몇 시간씩 어긋난다(백엔드는 항상 UTC로 저장).
    expect(formatElapsed("2026-09-18T11:55:00.000000", now)).toBe("5분 전");
  });

  it("handles a properly zoned timestamp the same way", () => {
    expect(formatElapsed("2026-09-18T11:55:00.000000Z", now)).toBe("5분 전");
  });

  it("shows '방금 전' for under a minute", () => {
    expect(formatElapsed("2026-09-18T11:59:30Z", now)).toBe("방금 전");
  });

  it("shows hours for over an hour", () => {
    expect(formatElapsed("2026-09-18T09:00:00Z", now)).toBe("3시간 전");
  });

  it("shows days for over a day", () => {
    expect(formatElapsed("2026-09-16T12:00:00Z", now)).toBe("2일 전");
  });
});
