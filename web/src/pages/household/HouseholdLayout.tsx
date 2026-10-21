import { useState } from "react";
import { NavLink, Outlet, useOutletContext, useParams } from "react-router";
import { ErrorText, Loading } from "../../components/ui";
import { useHousehold } from "../../features/households/hooks";
import type { HouseholdDetail } from "../../types/api";

const tab = ({ isActive }: { isActive: boolean }) =>
  `whitespace-nowrap rounded-xl px-3.5 py-1.5 text-sm font-medium transition-all duration-200 ${
    isActive
      ? "bg-white text-indigo-700 shadow-sm ring-1 ring-indigo-100"
      : "text-slate-500 hover:bg-white/70 hover:text-slate-900"
  }`;

export function HouseholdLayout() {
  const { householdId = "" } = useParams();
  const household = useHousehold(householdId);
  const [copied, setCopied] = useState(false);

  if (household.isLoading) return <Loading />;
  if (!household.data) return <ErrorText error={household.error ?? "Household not found"} />;
  const h = household.data;

  const copyCode = async () => {
    await navigator.clipboard?.writeText(h.invite_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <>
      <div className="relative mb-6 overflow-hidden rounded-3xl bg-linear-to-br from-indigo-600 via-violet-600 to-fuchsia-600 p-6 text-white shadow-xl shadow-indigo-500/20">
        <div className="pointer-events-none absolute -right-10 -top-16 h-48 w-48 rounded-full bg-white/15 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-20 left-1/3 h-40 w-40 rounded-full bg-fuchsia-300/30 blur-2xl" />
        <div className="relative flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-white/70">Household</p>
            <h1 className="mt-1 text-3xl font-extrabold tracking-tight">{h.name}</h1>
            <div className="mt-3 flex -space-x-2">
              {h.members.slice(0, 8).map((m) => (
                <span
                  key={m.id}
                  title={m.display_name}
                  className="flex h-8 w-8 items-center justify-center rounded-full bg-white/20 text-xs font-semibold ring-2 ring-white/40 backdrop-blur transition hover:z-10 hover:-translate-y-0.5 hover:bg-white/35"
                >
                  {m.display_name.slice(0, 1).toUpperCase()}
                </span>
              ))}
              <span className="pl-4 text-sm text-white/80">
                {h.members.length} {h.members.length === 1 ? "person" : "people"} · {h.timezone}
              </span>
            </div>
          </div>
          <button
            onClick={copyCode}
            className="rounded-2xl bg-white/15 px-4 py-2 text-left ring-1 ring-white/30 backdrop-blur transition hover:-translate-y-0.5 hover:bg-white/25"
            title="Copy invite code"
          >
            <span className="block text-[11px] font-medium uppercase tracking-widest text-white/70">
              {copied ? "Copied!" : "Invite code"}
            </span>
            <span className="font-mono text-lg font-semibold tracking-wider">{h.invite_code}</span>
          </button>
        </div>
      </div>
      <nav className="mb-6 flex gap-1 overflow-x-auto rounded-2xl bg-white/60 p-1 ring-1 ring-slate-900/5 backdrop-blur">
        <NavLink to="" end className={tab}>Today</NavLink>
        <NavLink to="activity" className={tab}>Activity</NavLink>
        <NavLink to="report" className={tab}>Report</NavLink>
        <NavLink to="schedule" className={tab}>Schedule</NavLink>
        <NavLink to="people" className={tab}>People</NavLink>
        <NavLink to="chores" className={tab}>Chores</NavLink>
        {h.my_role === "admin" && <NavLink to="history" className={tab}>History</NavLink>}
      </nav>
      <Outlet context={h} />
    </>
  );
}

export function useCurrentHousehold() {
  return useOutletContext<HouseholdDetail>();
}
