import { useState } from "react";
import { Button, Empty, ErrorText, Loading } from "../../components/ui";
import { useSchedule } from "../../features/chores/hooks";
import { formatDay } from "../../lib/format";
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
      <div className="mb-3 flex gap-2">
        {[7, 14, 28].map((n) => (
          <Button key={n} variant={n === days ? "primary" : "secondary"} onClick={() => setDays(n)}>
            {n} days
          </Button>
        ))}
      </div>
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2.5 font-medium">Day</th>
              {chores.map((c) => <th key={c.id} className="px-4 py-2.5 font-medium">{c.name}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((day, i) => (
              <tr key={day.date} className={`border-t border-slate-100 ${i === 0 ? "bg-indigo-50/50" : ""}`}>
                <td className="whitespace-nowrap px-4 py-2.5 font-medium">
                  {formatDay(day.date)} {i === 0 && <span className="text-xs text-indigo-600">today</span>}
                </td>
                {chores.map((c) => {
                  const slot = day.slots.find((s) => s.chore.id === c.id);
                  const mine = slot?.member.id === household.my_member_id;
                  return (
                    <td key={c.id} className={`whitespace-nowrap px-4 py-2.5 ${mine ? "font-semibold text-indigo-700" : ""}`}>
                      {slot ? slot.member.display_name : "—"} {slot?.status === "done" && "✓"}
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
