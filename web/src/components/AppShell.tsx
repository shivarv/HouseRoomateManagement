import { NavLink, Outlet, useMatch } from "react-router";
import { useAuth } from "../features/auth/AuthContext";
import { useHelpRequests } from "../features/help/hooks";
import { useDefaultHousehold } from "../features/households/hooks";
import { Button } from "./ui";

const link = ({ isActive }: { isActive: boolean }) =>
  `whitespace-nowrap rounded-xl px-3 py-1.5 text-sm font-medium transition-all duration-200 ${
    isActive
      ? "bg-linear-to-r from-indigo-500/10 to-fuchsia-500/10 text-indigo-700 ring-1 ring-indigo-200"
      : "text-slate-600 hover:bg-white/80 hover:text-slate-900"
  }`;

const HOUSE_TABS = [
  { path: "activity", label: "Activity" },
  { path: "report", label: "Report" },
  { path: "schedule", label: "Schedule" },
  { path: "people", label: "People" },
  { path: "chores", label: "Chores" },
] as const;

export function AppShell() {
  const { user, signOut } = useAuth();
  const help = useHelpRequests();
  const { households, house: defaultHouse } = useDefaultHousehold();
  // The house tabs act on the house I'm looking at; elsewhere, my default house.
  const viewing = useMatch("/households/:householdId/*")?.params.householdId;
  const house = households.data?.find((h) => h.id === viewing) ?? defaultHouse;
  const base = house ? `/households/${house.id}` : null;
  // The badge counts requests other people are waiting on.
  const waiting = (help.data ?? []).filter((r) => r.status === "open" && !r.is_mine).length;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-white/60 bg-white/70 backdrop-blur-lg">
        <div className="mx-auto flex max-w-4xl items-center gap-2 px-4 pt-3">
          <span className="flex items-center gap-2 whitespace-nowrap">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-linear-to-br from-indigo-500 to-fuchsia-500 text-base shadow-md shadow-indigo-500/30">
              🏠
            </span>
            <span className="text-lg font-extrabold tracking-tight">
              <span className="text-gradient">Roommates</span>
            </span>
          </span>
          <div className="ml-auto flex items-center gap-2">
            {user && (
              <span
                className="hidden h-8 w-8 items-center justify-center rounded-full bg-linear-to-br from-sky-400 to-indigo-500 text-sm font-semibold text-white shadow-sm sm:flex"
                title={user.name}
              >
                {user.name.slice(0, 1).toUpperCase()}
              </span>
            )}
            <Button variant="ghost" className="whitespace-nowrap" onClick={signOut}>
              Sign out
            </Button>
          </div>
        </div>
        <nav className="mx-auto flex max-w-4xl gap-1 overflow-x-auto px-4 py-2">
          <NavLink to="/" end className={link}>
            My day
          </NavLink>
          {base ? (
            HOUSE_TABS.map((t) => (
              <NavLink key={t.label} to={`${base}/${t.path}`} className={link}>
                {t.label}
              </NavLink>
            ))
          ) : (
            <NavLink to="/households" className={link}>
              Households
            </NavLink>
          )}
          <NavLink to="/notifications" className={link} title="Help requests">
            <span className="relative">
              🔔 Notifications
              {waiting > 0 && (
                <span className="absolute -right-3 -top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-fuchsia-600 px-1 text-[10px] font-bold text-white">
                  {waiting}
                </span>
              )}
            </span>
          </NavLink>
          {house?.my_role === "admin" && (
            <NavLink to={`${base}/settings`} className={(state) => `ml-auto ${link(state)}`}>
              ⚙ Settings
            </NavLink>
          )}
        </nav>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
