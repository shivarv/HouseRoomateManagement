import { Badge } from "../../components/ui";
import { formatTime, relativeDay } from "../../lib/format";
import type { OpenChore } from "../../types/api";
import { ChoreAvatar } from "./TaskCard";
import { useLogChore, useRemoveLog } from "./hooks";

/**
 * A chore nobody is assigned to (e.g. garbage): one button per person, fewest this year first.
 * Whoever did it taps their own name.
 */
export function OpenChoreCard({ item, today, myMemberId, showHousehold = false }: {
  item: OpenChore;
  today: string;
  myMemberId?: string;
  showHousehold?: boolean;
}) {
  const log = useLogChore();
  const remove = useRemoveLog();
  const last = item.last_done;
  const target = item.target_per_week;

  return (
    <div className="card-hover group rounded-2xl border border-white/70 bg-white/90 p-4 shadow-sm ring-1 ring-slate-900/5 backdrop-blur">
      <div className="flex items-center gap-4">
        <ChoreAvatar name={item.chore.name} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{item.chore.name}</span>
            <Badge tone="green">Anyone</Badge>
            {target !== null && (
              <Badge tone={item.this_week_count >= target ? "green" : "amber"}>
                {item.this_week_count}/{target} this week
              </Badge>
            )}
          </div>
          <p className="truncate text-sm text-slate-500">
            {last ? `Last done by ${last.member.display_name}, ${relativeDay(last.done_on, today)}` : "Not done yet"}
            {target === null && ` · ${item.this_week_count} this week`}
            {showHousehold && ` · ${item.household_name}`}
          </p>
        </div>
      </div>

      <p className="mt-4 text-xs text-slate-500">
        <span className="font-medium text-slate-600">Who did it?</span> Tap your name.
        {item.suggested && (
          <>
            {" "}Suggested next: <span className="text-gradient font-semibold">{item.suggested.display_name}</span>
            {item.suggested_reason && ` (${item.suggested_reason})`}
          </>
        )}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {item.people.map((p, i) => (
          <button
            key={p.member.id}
            disabled={log.isPending}
            onClick={() => log.mutate({ choreId: item.chore.id, memberId: p.member.id })}
            title={`${p.member.display_name}: ${p.this_year} this year, ${p.this_month} this month`}
            className={`flex flex-col items-start rounded-xl border px-3 py-1.5 text-left transition-all duration-200 hover:-translate-y-0.5 active:scale-95 disabled:opacity-50 ${
              i === 0
                ? "border-transparent bg-linear-to-br from-indigo-500 via-violet-500 to-fuchsia-500 text-white shadow-md shadow-indigo-500/30 hover:shadow-lg hover:shadow-fuchsia-500/30"
                : "border-slate-200 bg-white hover:border-indigo-300 hover:shadow-md hover:shadow-indigo-500/10"
            }`}
          >
            <span className={`text-sm font-semibold ${i !== 0 && p.member.id === myMemberId ? "text-indigo-700" : ""}`}>
              {p.member.display_name}
              {p.member.id === myMemberId && " (you)"}
            </span>
            <span className={`text-xs ${i === 0 ? "text-white/85" : "text-slate-500"}`}>
              {p.this_year} this year{i === 0 && " · ⭐ next"}
            </span>
          </button>
        ))}
      </div>

      {item.today_logs.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 text-xs">
          <span className="text-slate-500">Today:</span>
          {item.today_logs.map((entry) => (
            <span key={entry.id} className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-700 ring-1 ring-emerald-200">
              ✓ {entry.member.display_name} · {formatTime(entry.created_at)}
              <button
                className="ml-0.5 text-emerald-500 hover:text-red-600"
                title="Remove this entry (pressed by mistake)"
                disabled={remove.isPending}
                onClick={() => remove.mutate(entry.id)}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
