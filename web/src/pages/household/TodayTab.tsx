import { Empty, ErrorText, Loading } from "../../components/ui";
import { OpenChoreCard } from "../../features/chores/OpenChoreCard";
import { TaskCard } from "../../features/chores/TaskCard";
import { useHouseholdToday } from "../../features/chores/hooks";
import { formatDay } from "../../lib/format";
import { useCurrentHousehold } from "./HouseholdLayout";

export function TodayTab() {
  const household = useCurrentHousehold();
  const today = useHouseholdToday(household.id);

  if (today.isLoading) return <Loading />;
  const tasks = today.data?.tasks ?? [];
  const open = today.data?.open ?? [];
  const daily = tasks.filter((t) => t.chore.frequency === "daily");
  const weekly = tasks.filter((t) => t.chore.frequency === "weekly");

  return (
    <div className="space-y-8">
      <ErrorText error={today.error} />
      {tasks.length === 0 && open.length === 0 && (
        <Empty>No chores yet. Add people and chores in the People and Chores tabs.</Empty>
      )}

      {daily.length > 0 && today.data && (
        <section className="space-y-3">
          <h2 className="section-title">
            {formatDay(today.data.date, { weekday: "long", month: "long", day: "numeric" })}
          </h2>
          {daily.map((t) => <TaskCard key={t.id} task={t} />)}
        </section>
      )}

      {weekly.length > 0 && (
        <section className="space-y-3">
          <h2 className="section-title">This week</h2>
          {weekly.map((t) => <TaskCard key={t.id} task={t} />)}
        </section>
      )}

      {open.length > 0 && today.data && (
        <section className="space-y-3">
          <h2 className="section-title">Anyone can do</h2>
          {open.map((o) => <OpenChoreCard key={o.chore.id} item={o} today={today.data.date} myMemberId={household.my_member_id} />)}
        </section>
      )}
    </div>
  );
}
