import { useMemo, useState } from "react";
import { Empty, ErrorText, Loading } from "../../components/ui";
import { activityPlainText, activityText, type ActivityKind, type ActivityLine } from "../../features/chores/activityText";
import { useActivityMonth } from "../../features/chores/hooks";
import { formatMonth, formatTime, localIsoDate } from "../../lib/format";
import type { ActivityEvent } from "../../types/api";
import { useCurrentHousehold } from "./HouseholdLayout";

type KindFilter = "all" | "done" | "swaps" | "help" | "changes";

const kindStyle: Record<ActivityKind, string> = {
  done: "from-emerald-300 to-teal-500 shadow-teal-500/30",
  undo: "from-amber-300 to-orange-500 shadow-orange-500/30",
  swap: "from-fuchsia-300 to-pink-500 shadow-pink-500/30",
  help: "from-amber-200 to-orange-400 shadow-orange-500/30",
  settings: "from-indigo-300 to-violet-500 shadow-violet-500/30",
  people: "from-sky-300 to-blue-500 shadow-blue-500/30",
};

function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

/** Every update in the house for one month: who did what, and who marked it. */
export function ActivityTab() {
  const household = useCurrentHousehold();
  const isAdmin = household.my_role === "admin";
  const currentMonth = localIsoDate().slice(0, 7);
  const [month, setMonth] = useState(currentMonth);
  const [person, setPerson] = useState("all");
  const [kind, setKind] = useState<KindFilter>("all");
  const feed = useActivityMonth(household.id, month);

  const lines = useMemo(
    () => (feed.data ?? []).map((e) => ({ event: e, line: activityText(e) })),
    [feed.data],
  );
  const visible = lines.filter(({ event, line }) => {
    if (kind === "done" && line.kind !== "done" && line.kind !== "undo") return false;
    if (kind === "swaps" && line.kind !== "swap") return false;
    if (kind === "help" && line.kind !== "help") return false;
    if (kind === "changes" && ["done", "undo", "swap", "help"].includes(line.kind)) return false;
    if (person !== "all" && ![event.actor, event.subject, event.assignee].some((m) => m?.id === person)) return false;
    return true;
  });
  const choreCount = lines.filter((l) => l.line.kind === "done" || l.line.kind === "undo").length;
  const swapCount = lines.filter((l) => l.line.kind === "swap").length;
  const helpCount = lines.filter((l) => l.line.kind === "help").length;
  const changeCount = lines.length - choreCount - swapCount - helpCount;

  const groups = new Map<string, { event: ActivityEvent; line: ActivityLine }[]>();
  for (const item of visible) {
    const day = localIsoDate(new Date(item.event.created_at));
    groups.set(day, [...(groups.get(day) ?? []), item]);
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1 rounded-2xl bg-white/80 p-1 shadow-sm ring-1 ring-slate-900/5">
          <button
            className="rounded-xl px-2.5 py-1 text-slate-500 transition hover:bg-indigo-50 hover:text-indigo-700 disabled:opacity-30"
            disabled={!isAdmin}
            title={isAdmin ? "Previous month" : "Only admins can see past months"}
            onClick={() => setMonth(shiftMonth(month, -1))}
          >
            ‹
          </button>
          <span className="min-w-36 text-center text-sm font-semibold">{formatMonth(month)}</span>
          <button
            className="rounded-xl px-2.5 py-1 text-slate-500 transition hover:bg-indigo-50 hover:text-indigo-700 disabled:opacity-30"
            disabled={month >= currentMonth}
            title="Next month"
            onClick={() => setMonth(shiftMonth(month, 1))}
          >
            ›
          </button>
        </div>
        <div className="flex gap-1 rounded-2xl bg-white/80 p-1 text-sm shadow-sm ring-1 ring-slate-900/5">
          {(
            [
              ["all", `All · ${lines.length}`],
              ["done", `Chores · ${choreCount}`],
              ["swaps", `Swaps · ${swapCount}`],
              ["help", `Help · ${helpCount}`],
              ["changes", `Changes · ${changeCount}`],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              onClick={() => setKind(value)}
              className={`rounded-xl px-3 py-1 font-medium transition ${
                kind === value
                  ? "bg-linear-to-r from-indigo-500 to-fuchsia-500 text-white shadow-md shadow-indigo-500/30"
                  : "text-slate-600 hover:bg-indigo-50 hover:text-indigo-700"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <select
          value={person}
          onChange={(e) => setPerson(e.target.value)}
          className="rounded-2xl border-0 bg-white/80 px-3 py-2 text-sm shadow-sm ring-1 ring-slate-900/5 outline-none transition hover:ring-indigo-300 focus:ring-2 focus:ring-indigo-400"
        >
          <option value="all">Everyone</option>
          {household.members.map((m) => (
            <option key={m.id} value={m.id}>
              {m.id === household.my_member_id ? `${m.display_name} (you)` : m.display_name}
            </option>
          ))}
        </select>
      </div>

      <ErrorText error={feed.error} />
      {feed.isLoading ? (
        <Loading />
      ) : visible.length === 0 ? (
        <Empty>{lines.length === 0 ? `Nothing happened in ${formatMonth(month)} yet.` : "No updates match these filters."}</Empty>
      ) : (
        [...groups].map(([day, items]) => (
          <section key={day}>
            <h2 className="mb-2 section-title">{dayLabel(day)}</h2>
            <ol className="relative space-y-2 pl-6 before:absolute before:inset-y-2 before:left-[1.05rem] before:w-px before:bg-linear-to-b before:from-indigo-200 before:to-fuchsia-200">
              {items.map(({ event, line }) => (
                <li
                  key={event.id}
                  title={activityPlainText(line)}
                  className="card-hover group relative flex items-start gap-3 rounded-2xl border border-white/70 bg-white/90 px-4 py-3 text-sm shadow-sm ring-1 ring-slate-900/5"
                >
                  <span
                    className={`absolute -left-5 top-3 flex h-7 w-7 items-center justify-center rounded-full bg-linear-to-br text-xs shadow-md ring-4 ring-white transition-transform group-hover:scale-110 ${kindStyle[line.kind]}`}
                  >
                    {line.icon}
                  </span>
                  <p className="flex-1 pl-3 leading-relaxed text-slate-700">
                    {line.parts.map((part, i) =>
                      typeof part === "string" ? (
                        <span key={i}>{part}</span>
                      ) : "person" in part ? (
                        <strong
                          key={i}
                          className={part.person.id === household.my_member_id ? "text-gradient font-bold" : "font-semibold text-slate-900"}
                        >
                          {part.person.id === household.my_member_id ? `${part.person.display_name} (you)` : part.person.display_name}
                        </strong>
                      ) : (
                        <span key={i} className="rounded-md bg-indigo-50 px-1.5 py-0.5 font-medium text-indigo-700">
                          {part.chore}
                        </span>
                      ),
                    )}
                  </p>
                  <span className="whitespace-nowrap pt-0.5 text-xs text-slate-400">{formatTime(event.created_at)}</span>
                </li>
              ))}
            </ol>
          </section>
        ))
      )}
    </div>
  );
}

function dayLabel(isoDate: string): string {
  const today = localIsoDate();
  const yesterday = localIsoDate(new Date(Date.now() - 86_400_000));
  const pretty = new Date(`${isoDate}T12:00:00`).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
  if (isoDate === today) return `Today · ${pretty}`;
  if (isoDate === yesterday) return `Yesterday · ${pretty}`;
  return pretty;
}
