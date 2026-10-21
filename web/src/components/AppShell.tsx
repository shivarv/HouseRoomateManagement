import { NavLink, Outlet } from "react-router";
import { useAuth } from "../features/auth/AuthContext";
import { Button } from "./ui";

const link = ({ isActive }: { isActive: boolean }) =>
  `whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium ${isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:text-slate-900"}`;

export function AppShell() {
  const { user, signOut } = useAuth();
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center gap-1 px-4 py-3 sm:gap-2">
          <span className="mr-2 whitespace-nowrap font-semibold text-indigo-600 sm:mr-4">
            🏠<span className="hidden sm:inline"> Roommates</span>
          </span>
          <nav className="flex gap-1">
            <NavLink to="/" end className={link}>
              My day
            </NavLink>
            <NavLink to="/households" className={link}>
              Households
            </NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden text-sm text-slate-500 sm:inline">{user?.name}</span>
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
