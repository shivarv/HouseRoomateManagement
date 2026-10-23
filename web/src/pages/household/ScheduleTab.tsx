import { useState } from "react";
import { Empty, ErrorText, Loading } from "../../components/ui";
import { useSchedule } from "../../features/chores/hooks";
import { formatDay } from "../../lib/format";
import { subTab, subTabTray } from "../../lib/tabStyles";
import { useCurrentHousehold } from "./HouseholdLayout";

export function ScheduleTab() {
  const household = useCurrentHousehold();
  const [days, setDays] = useState(7);
  const schedule = useSchedule(household.id, days);

  if (schedule.isLoading) return <Loading />;
  const rows = schedule.data?.days ?? [];
  const chores = [...new Map(rows.flatMap((d) => d.slots.map((s) => [s.chore.id, s.chore]))).values()];
  if (chores.length === 0) return <Empty>No active chores with people assigned yet.</Empty>;

  return (
    <>
      <ErrorText error={schedule.error} />
      {/* Same tray and pills as the House tabs above, so the two rows line up. */}
      <div className="mb-4 flex">
        <div role="group" aria-label="How many days" className={subTabTray}>
          {[7, 14, 28].map((n) => (
            <button key={n} type="button" aria-pressed={n === days} className={subTab({ isActive: n === days })} onClick={() => setDays(n)}>
              {n} days
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto rounded-2xl border border-white/70 bg-white/90 shadow-sm ring-1 ring-slate-900/5 backdrop-blur">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2.5 font-medium">Day</th>
              {chores.map((c) => <th key={c.id} className="px-4 py-2.5 font-medium">{c.name}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((day, i) => (
              <tr key={day.date} className={`border-t border-slate-100 transition hover:bg-indigo-50/40 ${i === 0 ? "bg-linear-to-r from-indigo-50 to-fuchsia-50/40" : ""}`}>
                <td className="whitespace-nowrap px-4 py-2.5 font-medium">
                  {formatDay(day.date)} {i === 0 && <span className="text-xs text-indigo-600">today</span>}
                </td>
                {chores.map((c) => {
                  const slot = day.slots.find((s) => s.chore.id === c.id);
                  const mine = slot?.member.id === household.my_member_id;
                  return (
                    <td key={c.id} className={`whitespace-nowrap px-4 py-2.5 ${mine ? "font-semibold text-indigo-700" : ""}`}>
                      {slot ? slot.member.display_name : "—"} {slot?.status === "done" && "✓"}
                      {slot?.swapped_with && (
                        <span className="ml-1 cursor-help text-xs text-fuchsia-600" title={`Swapped with ${slot.swapped_with.display_name}`}>
                          ⇄
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
