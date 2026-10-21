function parseDay(isoDate: string): Date {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** Formats a backend YYYY-MM-DD date without shifting it through the browser's timezone. */
export function formatDay(
  isoDate: string,
  options: Intl.DateTimeFormatOptions = { weekday: "short", month: "short", day: "numeric" },
) {
  return parseDay(isoDate).toLocaleDateString(undefined, options);
}

/** "today", "yesterday", or "Mon, Oct 19", relative to the household's today. */
export function relativeDay(isoDate: string, todayIso: string): string {
  const days = Math.round((parseDay(todayIso).getTime() - parseDay(isoDate).getTime()) / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  return formatDay(isoDate);
}

export function formatTime(isoDateTime: string): string {
  return new Date(isoDateTime).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export function formatMonth(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

export function localIsoDate(date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function percent(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}

export function browserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
}
