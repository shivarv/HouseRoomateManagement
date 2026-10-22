import { useState } from "react";
import { Link } from "react-router";
import { Card, Empty, ErrorText, Loading, PageTitle } from "../components/ui";
import { useAuth } from "../features/auth/AuthContext";
import { OpenChoreCard } from "../features/chores/OpenChoreCard";
import { SwapRequests } from "../features/chores/SwapRequests";
import { TaskCard } from "../features/chores/TaskCard";
import { useMySwaps, useMyTasksToday } from "../features/chores/hooks";
import { useDefaultHousehold, useHouseholds, useSwitchHousehold } from "../features/households/hooks";
import { formatDay, localIsoDate } from "../lib/format";

/** Landing page after login: the in-app reminder of what *I* need to do today / this week. */
export function MyDayPage() {
  const { user } = useAuth();
  const households = useHouseholds();
  const mine = useMyTasksToday();
  const swaps = useMySwaps();

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
      <div className="relative mb-8 overflow-hidden rounded-3xl bg-linear-to-br from-indigo-600 via-violet-600 to-fuchsia-600 p-6 text-white shadow-xl shadow-indigo-500/20 sm:p-8">
        <div className="pointer-events-none absolute -right-12 -top-16 h-56 w-56 rounded-full bg-white/15 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-24 left-10 h-48 w-48 rounded-full bg-sky-300/30 blur-2xl" />
        <div className="relative">
          <p className="text-sm font-medium text-white/75">
            {new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
          </p>
          <h1 className="mt-1 text-3xl font-extrabold tracking-tight sm:text-4xl">Hi {user?.name} 👋</h1>
          <p className="mt-2 text-white/85">
            {tasks.length === 0
              ? "No turns for you right now."
              : pending === 0
                ? "All your turns are done. Nice!"
                : `You have ${pending} chore${pending > 1 ? "s" : ""} to do.`}
          </p>
          <div className="mt-5 flex flex-wrap items-end justify-between gap-4">
            <div className="grid grid-cols-3 gap-2 sm:w-96">
              <Stat label="Your turns" value={pending} />
              <Stat label="Everyone today" value={others.length + tasks.length} />
              <Stat label="Anyone can do" value={open.length} />
            </div>
            <HouseCard />
          </div>
        </div>
      </div>
      <ErrorText error={mine.error} />
      <SwapRequests swaps={swaps.data ?? []} showHousehold={(households.data?.length ?? 0) > 1} />

      <section className="space-y-3">
        <h2 className="section-title">Your turns</h2>
        {tasks.length === 0 ? (
          <Empty>Nothing for you today. Enjoy your day off 🎉</Empty>
        ) : (
          tasks.map((t) => <TaskCard key={t.id} task={t} showHousehold={multiHouse} />)
        )}
        {upcoming.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
            <span className="text-slate-500">📅 Your next turns:</span>
            {upcoming.map((u) => (
              <span
                key={`${u.household_id}-${u.chore.id}`}
                className="rounded-full border border-indigo-100 bg-white/90 px-3 py-1 shadow-sm transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md hover:shadow-indigo-500/10"
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
          <h2 className="section-title">Everyone today</h2>
          {others.map((t) => (
            <TaskCard key={t.id} task={t} showHousehold={multiHouse} />
          ))}
        </section>
      )}

      {open.length > 0 && (
        <section className="mt-8 space-y-3">
          <h2 className="section-title">Anyone can do</h2>
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
          <h2 className="section-title text-amber-700!">Missed earlier</h2>
          {overdue.map((t) => (
            <TaskCard key={t.id} task={t} overdue showHousehold={multiHouse} />
          ))}
        </section>
      )}

    </>
  );
}

/** "tomorrow" for the next day, otherwise e.g. "Fri, Oct 23". */
function dayWord(isoDate: string): string {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  return isoDate === localIsoDate(tomorrow) ? "tomorrow" : formatDay(isoDate);
}

/** The house the tabs act on: name, switcher (if I'm in several), invite code, add another. */
function HouseCard() {
  const { households, house } = useDefaultHousehold();
  const switchTo = useSwitchHousehold();
  const [copied, setCopied] = useState(false);
  if (!house) return null;
  const list = households.data ?? [];

  const copyCode = async () => {
    await navigator.clipboard?.writeText(house.invite_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="rounded-2xl bg-white/15 px-4 py-3 ring-1 ring-white/25 backdrop-blur">
      <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-widest text-white/70">
        🏠 Household
        <Link to="/households/new" className="rounded-md px-1.5 py-0.5 normal-case tracking-normal text-white/80 transition hover:bg-white/15 hover:text-white">
          + New or join
        </Link>
      </div>
      {list.length > 1 ? (
        <select
          aria-label="Switch household"
          value={house.id}
          onChange={(e) => switchTo(e.target.value)}
          className="mt-0.5 cursor-pointer rounded-lg bg-white/10 py-0.5 pr-1 text-lg font-bold text-white outline-none ring-1 ring-white/30 transition hover:bg-white/20 [&>option]:text-slate-900"
        >
          {list.map((h) => (
            <option key={h.id} value={h.id}>
              {h.name}
            </option>
          ))}
        </select>
      ) : (
        <p className="text-lg font-bold">{house.name}</p>
      )}
      <button onClick={copyCode} title="Copy invite code" className="mt-0.5 text-xs text-white/80 transition hover:text-white">
        {copied ? "Copied!" : <>Invite code <span className="font-mono font-semibold tracking-wider">{house.invite_code}</span></>}
      </button>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl bg-white/15 px-3 py-2 ring-1 ring-white/25 backdrop-blur transition hover:bg-white/25">
      <div className="text-2xl font-bold leading-tight">{value}</div>
      <div className="text-[11px] font-medium uppercase tracking-wide text-white/75">{label}</div>
    </div>
  );
}
