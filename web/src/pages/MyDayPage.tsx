import { Link } from "react-router";
import { Card, Empty, ErrorText, Loading, PageTitle } from "../components/ui";
import { useAuth } from "../features/auth/AuthContext";
import { TaskCard } from "../features/chores/TaskCard";
import { useMyTasksToday } from "../features/chores/hooks";
import { useHouseholds } from "../features/households/hooks";

/** Landing page after login: the in-app reminder of what *I* need to do today. */
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
            You're not in a household yet. <Link to="/households" className="font-medium text-indigo-600 hover:underline">Create one or join with an invite code</Link>.
          </p>
        </Card>
      </>
    );
  }

  const tasks = mine.data?.tasks ?? [];
  const overdue = mine.data?.overdue ?? [];
  const pending = tasks.filter((t) => t.status === "pending").length;
  const multiHouse = (households.data?.length ?? 0) > 1;

  return (
    <>
      <PageTitle
        title={`Hi ${user?.name} 👋`}
        subtitle={
          tasks.length === 0
            ? "Nothing assigned to you today."
            : pending === 0
              ? "All done for today. Nice!"
              : `You have ${pending} chore${pending > 1 ? "s" : ""} to do today.`
        }
      />
      <ErrorText error={mine.error} />

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Your tasks today</h2>
        {tasks.length === 0 ? (
          <Empty>Enjoy your day off 🎉</Empty>
        ) : (
          tasks.map((t) => <TaskCard key={t.id} task={t} canToggle showHousehold={multiHouse} />)
        )}
      </section>

      {overdue.length > 0 && (
        <section className="mt-8 space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-amber-700">Missed earlier</h2>
          {overdue.map((t) => <TaskCard key={t.id} task={t} canToggle overdue showHousehold={multiHouse} />)}
        </section>
      )}

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Households</h2>
        <div className="flex flex-wrap gap-2">
          {households.data?.map((h) => (
            <Link key={h.id} to={`/households/${h.id}`} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium hover:border-indigo-300">
              {h.name} →
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
