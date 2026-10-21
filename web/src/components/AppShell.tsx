import { NavLink, Outlet } from "react-router";
import { useAuth } from "../features/auth/AuthContext";
import { Button } from "./ui";

const link = ({ isActive }: { isActive: boolean }) =>
  `whitespace-nowrap rounded-xl px-3 py-1.5 text-sm font-medium transition-all duration-200 ${
    isActive
      ? "bg-linear-to-r from-indigo-500/10 to-fuchsia-500/10 text-indigo-700 ring-1 ring-indigo-200"
      : "text-slate-600 hover:bg-white/80 hover:text-slate-900"
  }`;

export function AppShell() {
  const { user, signOut } = useAuth();
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-white/60 bg-white/70 backdrop-blur-lg">
        <div className="mx-auto flex max-w-4xl items-center gap-1 px-4 py-3 sm:gap-2">
          <span className="mr-2 flex items-center gap-2 whitespace-nowrap sm:mr-4">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-linear-to-br from-indigo-500 to-fuchsia-500 text-base shadow-md shadow-indigo-500/30">
              🏠
            </span>
            <span className="hidden text-lg font-extrabold tracking-tight sm:inline">
              <span className="text-gradient">Roommates</span>
            </span>
          </span>
          <nav className="flex gap-1">
            <NavLink to="/" end className={link}>
              My day
            </NavLink>
            <NavLink to="/households" className={link}>
              Households
            </NavLink>
          </nav>
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
      </header>
      <main className="mx-auto max-w-4xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
