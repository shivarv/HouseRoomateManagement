import { NavLink, Outlet } from "react-router";
import { useCurrentHousehold } from "./HouseholdLayout";

const section = ({ isActive }: { isActive: boolean }) =>
  `whitespace-nowrap rounded-xl px-3.5 py-1.5 text-sm font-medium transition-all duration-200 ${
    isActive
      ? "bg-linear-to-r from-indigo-500 to-fuchsia-500 text-white shadow-md shadow-indigo-500/30"
      : "text-slate-600 hover:bg-white/70 hover:text-slate-900"
  }`;

/** 🏡 House: who's in the house, whose turn is when, and how everyone's doing. */
export function HouseLayout() {
  const household = useCurrentHousehold();
  return (
    <div className="space-y-6">
      <nav className="flex flex-wrap items-center gap-1">
        <NavLink to="schedule" className={section}>
          🗓️ Schedule
        </NavLink>
        <NavLink to="report" className={section}>
          📊 Report
        </NavLink>
        <NavLink to="people" className={section}>
          👥 People
        </NavLink>
      </nav>
      <Outlet context={household} />
    </div>
  );
}
