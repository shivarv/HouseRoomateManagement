import type { BillFrequency } from "../../types/api";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
/** Stored as 31: the backend uses each month's last day (30th, 31st, Feb 28/29). */
export const LAST_DAY = 31;

const fieldClass =
  "rounded-xl border border-slate-200 bg-white/90 px-3 py-2 text-sm shadow-sm outline-none transition hover:border-indigo-300 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15";

/** "Monthly on the 5th" · "Every Friday" · "Monthly on the last day" */
export function dueText(frequency: BillFrequency, dueDay: number): string {
  if (frequency === "daily") return "Every day";
  if (frequency === "weekly") return `Every ${WEEKDAYS[dueDay - 1] ?? "Monday"}`;
  return dueDay > 28 ? "Monthly on the last day" : `Monthly on day ${dueDay}`;
}

/**
 * "Due [ 5 ▾ ]": days 1–28, then "Last day of month" (29–31 would skip short months).
 * Weekly: "Due [ Friday ▾ ]". Daily: due the same day.
 */
export function DueDayField({
  frequency,
  value,
  onChange,
}: {
  frequency: BillFrequency;
  value: number;
  onChange: (day: number) => void;
}) {
  if (frequency === "daily") return <span className="text-sm text-slate-500">Due the same day</span>;
  return (
    <label className="flex items-center gap-2 text-sm font-medium text-slate-600">
      Due
      {frequency === "monthly" ? (
        <select className={`${fieldClass} w-40`} value={value > 28 ? LAST_DAY : value} onChange={(e) => onChange(Number(e.target.value))}>
          {Array.from({ length: 28 }, (_, i) => i + 1).map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
          <option value={LAST_DAY}>Last day of month</option>
        </select>
      ) : (
        <select className={`${fieldClass} w-36`} value={value} onChange={(e) => onChange(Number(e.target.value))}>
          {WEEKDAYS.map((d, i) => (
            <option key={d} value={i + 1}>
              {d}
            </option>
          ))}
        </select>
      )}
    </label>
  );
}
