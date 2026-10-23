import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { NavLink, Outlet, useLocation, useMatch, useNavigate } from "react-router";
import { chatApi } from "../api/chat";
import { useAuth } from "../features/auth/AuthContext";
import { useHelpRequests } from "../features/help/hooks";
import { useDefaultHousehold, useSwitchHousehold } from "../features/households/hooks";
import { unsavedChanges } from "../lib/unsavedChanges";
import type { Household } from "../types/api";
import { WelcomePage } from "../pages/WelcomePage";
import { Button } from "./ui";

const link = ({ isActive }: { isActive: boolean }) =>
  `shrink-0 snap-start whitespace-nowrap rounded-xl px-2.5 py-1.5 text-sm font-medium transition-all duration-200 ${
    isActive
      ? "bg-linear-to-r from-indigo-500/10 to-fuchsia-500/10 text-indigo-700 ring-1 ring-indigo-200"
      : "text-slate-600 hover:bg-white/80 hover:text-slate-900"
  }`;

const HOUSE_TABS = [
  { path: "reminders", label: "🧾 Reminders" },
  { path: "activity", label: "📰 Activity" },
  { path: "house", label: "🏡 House" }, // Schedule, Report and People
  { path: "groceries", label: "🛒 Groceries" },
  { path: "chat", label: "💬 Chat" },
] as const;

const NEW_GUIDED = "__new-guided";
const NEW_QUICK = "__new-quick";

/** Two of my houses can share a name (mine and one I joined): tell them apart by address. */
function houseLabel(h: Household, all: Household[]): string {
  const clash = all.some((o) => o.id !== h.id && o.name.toLowerCase() === h.name.toLowerCase());
  return clash && h.address ? `${h.name} · ${h.address}` : h.name;
}

export function AppShell() {
  const { user, signOut } = useAuth();
  const help = useHelpRequests();
  const { households, house: defaultHouse } = useDefaultHousehold();
  const switchTo = useSwitchHousehold();
  const navigate = useNavigate();
  // The house dropdown also starts a new home. On those pages it shows that choice; anywhere
  // else (e.g. after clicking a tab) it shows my house again, and the tabs act on that house.
  const { pathname } = useLocation();
  const adding = pathname.startsWith("/households/new/setup") ? NEW_GUIDED : pathname.startsWith("/households/new") ? NEW_QUICK : null;
  const pickHouse = (value: string) => {
    if (value === NEW_GUIDED || value === NEW_QUICK) {
      if (unsavedChanges.confirmLeave()) navigate(value === NEW_GUIDED ? "/households/new/setup" : "/households/new");
      return; // a cancelled leave keeps the current choice: the dropdown follows the page
    }
    if (adding) {
      // Leaving "create" or "join" for a house: show that house's day.
      if (!unsavedChanges.confirmLeave()) return;
      switchTo(value);
      navigate("/");
      return;
    }
    switchTo(value);
  };
  // The house tabs act on the house I'm looking at; elsewhere, my default house.
  const viewing = useMatch("/households/:householdId/*")?.params.householdId;
  const house = households.data?.find((h) => h.id === viewing) ?? defaultHouse;
  const base = house ? `/households/${house.id}` : null;
  // The badge counts requests other people are waiting on.
  const waiting = (help.data ?? []).filter((r) => r.status === "open" && !r.is_mine).length;
  // On phones the tabs scroll sideways: keep the one I'm on in view.
  const nav = useRef<HTMLElement>(null);
  // Unread chat messages in the house the tabs act on.
  const unread = useQuery({
    queryKey: ["chat-unread", house?.id],
    queryFn: () => chatApi.unread(house!.id),
    enabled: !!house,
    refetchInterval: 20_000,
  });
  const chatUnread = unread.data?.count ?? 0;
  // Signed in but in no home yet: no tabs, just a nudge to create one or join one.
  const noHouse = !households.isLoading && (households.data?.length ?? 0) === 0;
  // A load or reload always starts on my default house: half-done "create" or "join" pages
  // aren't kept (nothing was created yet), so they go back to My day. No house yet: stay.
  const firstLoad = useRef(true);
  useEffect(() => {
    if (!firstLoad.current || households.isLoading) return;
    firstLoad.current = false;
    if (adding && (households.data?.length ?? 0) > 0) navigate("/", { replace: true });
  }, [adding, households.isLoading, households.data, navigate]);
  useEffect(() => {
    nav.current?.querySelector('[aria-current="page"]')?.scrollIntoView({ inline: "center", block: "nearest" });
  }, [pathname]);

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
          {/* Which house the tabs act on, from any page; also where a new home is started. */}
          {house && (
            <select
              aria-label="Switch household, or start a new one"
              value={adding ?? house.id}
              onChange={(e) => pickHouse(e.target.value)}
              className="min-w-0 max-w-56 cursor-pointer truncate rounded-xl bg-white/80 px-2.5 py-1.5 text-sm font-medium text-slate-700 outline-none ring-1 ring-slate-200 transition hover:ring-indigo-300 focus:ring-indigo-400"
            >
              <optgroup label="Your homes">
                {households.data!.map((h) => (
                  <option key={h.id} value={h.id}>
                    🏠 {houseLabel(h, households.data!)}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Add a home">
                <option value={NEW_GUIDED}>✨ Create a new home</option>
                <option value={NEW_QUICK}>🔑 Join with an invite code</option>
              </optgroup>
            </select>
          )}
          <div className="ml-auto flex items-center gap-2">
            {user && (
              <NavLink
                to="/profile"
                className="hidden h-8 w-8 items-center justify-center rounded-full bg-linear-to-br from-sky-400 to-indigo-500 text-sm font-semibold text-white shadow-sm transition hover:ring-2 hover:ring-indigo-300 sm:flex"
                title={`${user.name} · your profile`}
              >
                {user.name.slice(0, 1).toUpperCase()}
              </NavLink>
            )}
            <Button variant="ghost" className="whitespace-nowrap" onClick={signOut}>
              Sign out
            </Button>
          </div>
        </div>
        {noHouse && (
          // No home yet: the tabs are there to show what's coming, but locked until I create or join one.
          <nav aria-label="Tabs (create or join a home first)" className="mx-auto flex max-w-4xl snap-x gap-1 overflow-x-auto px-4 py-2 [scrollbar-width:none] md:flex-wrap md:overflow-visible [&::-webkit-scrollbar]:hidden">
            {["☀️ My day", ...HOUSE_TABS.map((t) => t.label), "🔔 Notifications"].map((label) => (
              <span
                key={label}
                aria-disabled="true"
                title="Create or join a home first"
                className="cursor-not-allowed select-none whitespace-nowrap rounded-xl px-3 py-1.5 text-sm font-medium text-slate-400 opacity-60"
              >
                🔒 {label}
              </span>
            ))}
          </nav>
        )}
        {!noHouse && (
          <div className="mx-auto flex max-w-4xl items-center">
            <div className="relative min-w-0 flex-1">
              {/* Phones: one swipeable row (the fade says there's more). Wider screens: wrap, all visible. */}
              <nav
                ref={nav}
                className="flex snap-x gap-1 overflow-x-auto px-4 py-2 [scrollbar-width:none] md:flex-wrap md:overflow-visible [&::-webkit-scrollbar]:hidden"
              >
                <NavLink to="/" end className={link}>
                  ☀️ My day
                </NavLink>
                {base ? (
                  HOUSE_TABS.map((t) => (
                    <NavLink key={t.label} to={`${base}/${t.path}`} className={link}>
                      {t.path === "chat" && chatUnread > 0 ? (
                        <span className="relative">
                          {t.label}
                          <span className="absolute -right-3 -top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-fuchsia-600 px-1 text-[10px] font-bold text-white">
                            {chatUnread > 99 ? "99+" : chatUnread}
                          </span>
                        </span>
                      ) : (
                        t.label
                      )}
                    </NavLink>
                  ))
                ) : (
                  <NavLink to="/households" className={link}>
                    Households
                  </NavLink>
                )}
                <NavLink to="/notifications" className={link} title="Notifications and help requests">
                  <span className="relative">
                    🔔 Notifications
                    {waiting > 0 && (
                      <span className="absolute -right-3 -top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-fuchsia-600 px-1 text-[10px] font-bold text-white">
                        {waiting}
                      </span>
                    )}
                  </span>
                </NavLink>
              </nav>
              <div className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-linear-to-l from-white/90 to-transparent md:hidden" />
            </div>
            {/* Under Sign out, always in view for admins; only the tabs beside it scroll. */}
            {house?.my_role === "admin" && (
              <div className="shrink-0 pr-4">
                <NavLink
                  to={`${base}/settings`}
                  title="House settings (admins)"
                  className={({ isActive }) =>
                    `flex items-center gap-1 whitespace-nowrap rounded-xl px-3 py-1.5 text-sm font-semibold shadow-sm transition ${
                      isActive
                        ? "bg-linear-to-r from-indigo-500 to-fuchsia-500 text-white shadow-indigo-500/30"
                        : "bg-white text-indigo-700 ring-1 ring-indigo-200 hover:bg-indigo-50"
                    }`
                  }
                >
                  ⚙<span className="hidden sm:inline">Settings</span>
                </NavLink>
              </div>
            )}
          </div>
        )}
      </header>
      <main className="mx-auto max-w-4xl px-4 py-8">
        {noHouse && !pathname.startsWith("/households/new") && pathname !== "/profile" ? <WelcomePage /> : <Outlet />}
      </main>
    </div>
  );
}
