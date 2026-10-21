import { useState } from "react";
import { NavLink, Outlet, useOutletContext, useParams } from "react-router";
import { Badge, ErrorText, Loading } from "../../components/ui";
import { useHousehold } from "../../features/households/hooks";
import type { HouseholdDetail } from "../../types/api";

const tab = ({ isActive }: { isActive: boolean }) =>
  `whitespace-nowrap border-b-2 px-1 pb-2 text-sm font-medium ${isActive ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-800"}`;

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
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{h.name}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {h.members.length} {h.members.length === 1 ? "person" : "people"} · {h.timezone}
          </p>
        </div>
        <button onClick={copyCode} className="text-left text-sm text-slate-500 hover:text-slate-800" title="Copy invite code">
          Invite code <Badge tone="indigo">{h.invite_code}</Badge> {copied && <span className="text-emerald-600">Copied</span>}
        </button>
      </div>
      <nav className="mb-6 flex gap-5 overflow-x-auto border-b border-slate-200">
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
