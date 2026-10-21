import { Link } from "react-router";
import { Card, Empty, ErrorText, Loading, PageTitle } from "../components/ui";
import { useAuth } from "../features/auth/AuthContext";
import { OpenChoreCard } from "../features/chores/OpenChoreCard";
import { TaskCard } from "../features/chores/TaskCard";
import { useMyTasksToday } from "../features/chores/hooks";
import { useHouseholds } from "../features/households/hooks";
import { formatDay, localIsoDate } from "../lib/format";

/** Landing page after login: the in-app reminder of what *I* need to do today / this week. */
export function MyDayPage() {
  const { user } = useAuth();
  const households = useHouseholds();
  const mine = useMyTasksToday();

  if (households.isLoading || mine.isLoading) return <Loading />;
  if (households.data?.length === 0) {
    return (
      <>
        <PageTitle title={`Hi ${user?.name} 👋`} />
        <Card>
          <p className="text-sm text-slate-600">
            You're not in a household yet.{" "}
            <Link to="/households" className="font-medium text-indigo-600 hover:underline">
              Create one or join with an invite code
            </Link>
            .
          </p>
        </Card>
      </>
    );
  }

  const tasks = mine.data?.tasks ?? [];
  const others = mine.data?.others ?? [];
  const upcoming = mine.data?.upcoming ?? [];
  const overdue = mine.data?.overdue ?? [];
  const open = mine.data?.open ?? [];
  const pending = tasks.filter((t) => t.status === "pending").length;
  const multiHouse = (households.data?.length ?? 0) > 1;

  return (
    <>
      <PageTitle
        title={`Hi ${user?.name} 👋`}
        subtitle={
          tasks.length === 0
            ? "No turns for you right now."
            : pending === 0
              ? "All your turns are done. Nice!"
              : `You have ${pending} chore${pending > 1 ? "s" : ""} to do.`
        }
      />
      <ErrorText error={mine.error} />

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Your turns</h2>
        {tasks.length === 0 ? (
          <Empty>Nothing for you today. Enjoy your day off 🎉</Empty>
        ) : (
          tasks.map((t) => <TaskCard key={t.id} task={t} showHousehold={multiHouse} />)
        )}
        {upcoming.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
            <span className="text-slate-500">Your next turns:</span>
            {upcoming.map((u) => (
              <span
                key={`${u.household_id}-${u.chore.id}`}
                className="rounded-full border border-slate-200 bg-white px-3 py-1"
                title={formatDay(u.due_date, { weekday: "long", month: "long", day: "numeric" })}
              >
                <span className="font-medium">{u.chore.name}</span> ·{" "}
                {u.chore.frequency === "weekly" ? `week of ${formatDay(u.due_date)}` : dayWord(u.due_date)}
                {multiHouse && ` · ${u.household_name}`}
              </span>
            ))}
          </div>
        )}
      </section>

      {others.length > 0 && (
        <section className="mt-8 space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Everyone today</h2>
          {others.map((t) => (
            <TaskCard key={t.id} task={t} showHousehold={multiHouse} />
          ))}
        </section>
      )}

      {open.length > 0 && (
        <section className="mt-8 space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Anyone can do</h2>
          {open.map((o) => (
            <OpenChoreCard
              key={o.chore.id}
              item={o}
              today={localIsoDate()}
              myMemberId={households.data?.find((h) => h.id === o.household_id)?.my_member_id}
              showHousehold={multiHouse}
            />
          ))}
        </section>
      )}

      {overdue.length > 0 && (
        <section className="mt-8 space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-amber-700">Missed earlier</h2>
          {overdue.map((t) => (
            <TaskCard key={t.id} task={t} overdue showHousehold={multiHouse} />
          ))}
        </section>
      )}

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Households</h2>
        <div className="flex flex-wrap gap-2">
          {households.data?.map((h) => (
            <Link
              key={h.id}
              to={`/households/${h.id}`}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium hover:border-indigo-300"
            >
              {h.name} →
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}

/** "tomorrow" for the next day, otherwise e.g. "Fri, Oct 23". */
function dayWord(isoDate: string): string {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  return isoDate === localIsoDate(tomorrow) ? "tomorrow" : formatDay(isoDate);
}
