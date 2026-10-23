import { NavLink, Outlet } from "react-router";
import { subTab, subTabTray } from "../../lib/tabStyles";
import { useCurrentHousehold } from "./HouseholdLayout";

const section = subTab;

/** 🏡 House: who's in the house, whose turn is when, how everyone's doing, and a dashboard of it all. */
export function HouseLayout() {
  const household = useCurrentHousehold();
  return (
    <div className="space-y-6">
      <nav className={subTabTray}>
        <NavLink to="schedule" className={section}>
          🗓️ Schedule
        </NavLink>
        <NavLink to="dashboard" className={section}>
          📈 Dashboard
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
