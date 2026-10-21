import { Empty, ErrorText, Loading } from "../../components/ui";
import { activityText } from "../../features/chores/activityText";
import { useActivity } from "../../features/chores/hooks";
import { formatTime } from "../../lib/format";
import type { ActivityEvent } from "../../types/api";
import { useCurrentHousehold } from "./HouseholdLayout";

/** Everything that happened in the house, newest first. Visible to everyone. */
export function ActivityTab() {
  const household = useCurrentHousehold();
  const feed = useActivity(household.id);

  if (feed.isLoading) return <Loading />;
  const events = feed.data ?? [];
  if (events.length === 0) return <Empty>No activity yet.</Empty>;

  const groups = new Map<string, ActivityEvent[]>();
  for (const e of events) {
    const day = new Date(e.created_at).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
    groups.set(day, [...(groups.get(day) ?? []), e]);
  }

  return (
    <div className="space-y-6">
      <ErrorText error={feed.error} />
      {[...groups].map(([day, items]) => (
        <section key={day}>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">{day}</h2>
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white shadow-sm">
            {items.map((e) => {
              const { icon, text } = activityText(e);
              return (
                <li key={e.id} className="flex items-start gap-3 px-4 py-2.5 text-sm">
                  <span className="w-5 text-center">{icon}</span>
                  <span className="flex-1">{text}</span>
                  <span className="whitespace-nowrap text-xs text-slate-400">{formatTime(e.created_at)}</span>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      {events.length >= 50 && <p className="text-center text-xs text-slate-400">Showing the latest 50 updates.</p>}
    </div>
  );
}
