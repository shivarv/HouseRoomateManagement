import { Empty, ErrorText, Loading } from "../../components/ui";
import { TaskCard } from "../../features/chores/TaskCard";
import { useHouseholdToday } from "../../features/chores/hooks";
import { formatDay } from "../../lib/format";
import { useCurrentHousehold } from "./HouseholdLayout";

export function TodayTab() {
  const household = useCurrentHousehold();
  const today = useHouseholdToday(household.id);
  const isAdmin = household.my_role === "admin";

  if (today.isLoading) return <Loading />;
  const tasks = today.data?.tasks ?? [];

  return (
    <section className="space-y-3">
      <ErrorText error={today.error} />
      {today.data && (
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          {formatDay(today.data.date, { weekday: "long", month: "long", day: "numeric" })}
        </h2>
      )}
      {tasks.length === 0 ? (
        <Empty>No chores today. Add people and chores in the People and Chores tabs.</Empty>
      ) : (
        tasks.map((t) => <TaskCard key={t.id} task={t} canToggle={t.is_mine || isAdmin} />)
      )}
    </section>
  );
}
