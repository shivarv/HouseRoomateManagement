import { useEffect, useState } from "react";
import { Link, Outlet, useOutletContext, useParams } from "react-router";
import { ErrorText, Loading } from "../../components/ui";
import { useHousehold, useHouseholds, useSwitchHousehold } from "../../features/households/hooks";
import { lastHousehold } from "../../lib/lastHousehold";
import type { HouseholdDetail } from "../../types/api";

export function HouseholdLayout() {
  const { householdId = "" } = useParams();
  const household = useHousehold(householdId);
  const households = useHouseholds();
  const switchTo = useSwitchHousehold();
  const [copied, setCopied] = useState(false);

  // Remember this house (e.g. opened from a link) so the tabs open it next time.
  useEffect(() => {
    if (household.data) lastHousehold.set(household.data.id);
  }, [household.data]);

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
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-widest text-white/70">
              {(households.data?.length ?? 0) > 1 ? (
                <select
                  aria-label="Switch household"
                  value={h.id}
                  onChange={(e) => switchTo(e.target.value)}
                  className="select-on-dark cursor-pointer rounded-lg bg-white/15 px-2 py-1 font-semibold uppercase tracking-widest text-white outline-none ring-1 ring-white/30 transition hover:bg-white/25 [&>option]:text-slate-900"
                >
                  {households.data!.map((other) => (
                    <option key={other.id} value={other.id}>
                      {other.name}
                    </option>
                  ))}
                </select>
              ) : (
                <span>Household</span>
              )}
              <Link to="/households/new" className="rounded-lg px-2 py-1 normal-case tracking-normal text-white/80 transition hover:bg-white/15 hover:text-white">
                + New or join
              </Link>
            </div>
            <h1 className="mt-1 text-3xl font-extrabold tracking-tight">{h.name}</h1>
            {h.address && <p className="mt-0.5 text-sm text-white/80">📍 {h.address}</p>}
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
      <Outlet context={h} />
    </>
  );
}

export function useCurrentHousehold() {
  return useOutletContext<HouseholdDetail>();
}
