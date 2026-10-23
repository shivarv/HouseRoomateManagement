import { createContext, useContext, useEffect, type ReactNode } from "react";
import { Outlet, useLocation, useOutletContext, useParams } from "react-router";
import { ErrorText, Loading } from "../../components/ui";
import { useHousehold, useHouseholds, useSwitchHousehold } from "../../features/households/hooks";
import { lastHousehold } from "../../lib/lastHousehold";
import type { HouseholdDetail } from "../../types/api";

/** Each house tab's header: its name and what it's for. Keyed by the path after /households/:id/. */
const TABS: Record<string, { title: string; about: (house: string) => string }> = {
  reminders: {
    title: "🧾 Reminders",
    about: (house) => `What needs doing in ${house}: bills that are due (and who pays), then today's chores — yours first.`,
  },
  activity: {
    title: "📰 Activity",
    about: (house) => `Everything that happened in ${house}: chores done, swaps, bills paid, and people joining.`,
  },
  house: {
    title: "🏡 House",
    about: (house) => `How ${house} runs: the chore schedule, who did what this month, and the people who live here.`,
  },
  groceries: {
    title: "🛒 Groceries",
    about: (house) => `${house}'s shared shopping list. Add what's running low; tick it off once it's bought.`,
  },
  chat: { title: "💬 Chat", about: (house) => `Talk with everyone in ${house}. Only people in the house can see it.` },
  settings: {
    title: "⚙️ Settings",
    about: (house) => `For admins: ${house}'s details, roommates and invites, chores, groceries and reminders.`,
  },
};

export function HouseholdLayout() {
  const { householdId = "" } = useParams();
  const household = useHousehold(householdId);
  const households = useHouseholds();
  const switchTo = useSwitchHousehold();
  const { pathname } = useLocation();

  // Remember this house (e.g. opened from a link) so the tabs open it next time.
  useEffect(() => {
    if (household.data) lastHousehold.set(household.data.id);
  }, [household.data]);

  if (household.isLoading) return <Loading />;
  if (!household.data) return <ErrorText error={household.error ?? "Household not found"} />;
  const h = household.data;

  const segment = pathname.split("/")[3] ?? "";
  const tab = TABS[segment] ?? TABS.reminders;
  const multiHouse = (households.data?.length ?? 0) > 1;

  return (
    <>
      {/* Like My day's header: what this tab is for, in this house. Chat skips it: the chat fills the screen (its own header names the house). */}
      <div className={`relative mb-8 overflow-hidden rounded-3xl ${segment === "chat" ? "hidden" : ""} bg-linear-to-br from-indigo-600 via-violet-600 to-fuchsia-600 p-6 text-white shadow-xl shadow-indigo-500/20 sm:p-8`}>
        <div className="pointer-events-none absolute -right-12 -top-16 h-56 w-56 rounded-full bg-white/15 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-24 left-10 h-48 w-48 rounded-full bg-sky-300/30 blur-2xl" />
        <div className="relative">
          <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-white/75">
            {multiHouse ? (
              <select
                aria-label="Switch household"
                value={h.id}
                onChange={(e) => switchTo(e.target.value)}
                className="select-on-dark cursor-pointer rounded-lg bg-white/15 px-2 py-1 font-semibold text-white outline-none ring-1 ring-white/30 transition hover:bg-white/25 [&>option]:text-slate-900"
              >
                {households.data!.map((other) => (
                  <option key={other.id} value={other.id}>
                    {other.name}
                  </option>
                ))}
              </select>
            ) : (
              <span>🏠 {h.name}</span>
            )}
            <span>
              · 👥 {h.members.length} {h.members.length === 1 ? "person" : "people"}
            </span>
          </div>
          <h1 className="mt-1 text-3xl font-extrabold tracking-tight sm:text-4xl">{tab.title}</h1>
          <p className="mt-2 max-w-2xl text-white/85">{tab.about(h.name)}</p>
        </div>
      </div>
      <Outlet context={h} />
    </>
  );
}

/** For house screens shown outside a house page (e.g. Chores inside My day). */
const CurrentHousehold = createContext<HouseholdDetail | null>(null);

export function CurrentHouseholdProvider({ household, children }: { household: HouseholdDetail; children: ReactNode }) {
  return <CurrentHousehold.Provider value={household}>{children}</CurrentHousehold.Provider>;
}

/** The house a house screen is about: from a surrounding provider, else the house page's outlet. */
export function useCurrentHousehold() {
  const provided = useContext(CurrentHousehold);
  const fromPage = useOutletContext<HouseholdDetail>();
  return provided ?? fromPage;
}
