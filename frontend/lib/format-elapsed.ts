/** 백엔드(datetime.utcnow() 기반)가 보내는, 타임존 표기가 없는 ISO 문자열을
 * UTC로 해석한다. "Z"/offset이 없으면 브라우저가 로컬 시간대로 오해석해
 * 실제 경과 시간과 몇 시간씩 어긋나는 문제를 막는다. */
function parseAsUtc(isoTimestamp: string): Date {
  const hasTimezone = /[Zz]|[+-]\d{2}:?\d{2}$/.test(isoTimestamp);
  return new Date(hasTimezone ? isoTimestamp : `${isoTimestamp}Z`);
}

/** ISO 타임스탬프로부터 경과 시간을 "n분 전" 형태로 표시한다. */
export function formatElapsed(isoTimestamp: string, now: Date = new Date()): string {
  const then = parseAsUtc(isoTimestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);

  if (diffMinutes < 1) return "방금 전";
  if (diffMinutes < 60) return `${diffMinutes}분 전`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}시간 전`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}일 전`;
}
