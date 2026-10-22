import { Navigate, Route, Routes } from "react-router";
import { AppShell } from "./components/AppShell";
import { AuthPage } from "./pages/AuthPage";
import { HouseholdsPage } from "./pages/HouseholdsPage";
import { MyDayPage } from "./pages/MyDayPage";
import { ActivityTab } from "./pages/household/ActivityTab";
import { ChoresTab } from "./pages/household/ChoresTab";
import { HouseholdLayout } from "./pages/household/HouseholdLayout";
import { PeopleTab } from "./pages/household/PeopleTab";
import { HistoryTab, ReportTab } from "./pages/household/ReportTab";
import { ScheduleTab } from "./pages/household/ScheduleTab";
import { HouseDetailsSettings, SettingsLayout } from "./pages/household/SettingsPages";
import { TodayTab } from "./pages/household/TodayTab";
import { RequireAuth } from "./routes/RequireAuth";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/register" element={<AuthPage mode="register" />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<MyDayPage />} />
        <Route path="households" element={<HouseholdsPage />} />
        <Route path="households/:householdId" element={<HouseholdLayout />}>
          <Route index element={<TodayTab />} />
          <Route path="activity" element={<ActivityTab />} />
          <Route path="report" element={<ReportTab />} />
          <Route path="schedule" element={<ScheduleTab />} />
          <Route path="people" element={<PeopleTab />} />
          <Route path="chores" element={<ChoresTab />} />
          {/* Admin-only configuration, kept apart from the everyday tabs. */}
          <Route path="settings" element={<SettingsLayout />}>
            <Route index element={<HouseDetailsSettings />} />
            <Route path="people" element={<PeopleTab manage />} />
            <Route path="chores" element={<ChoresTab manage />} />
            <Route path="history" element={<HistoryTab />} />
          </Route>
          <Route path="history" element={<Navigate to="../settings/history" replace />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
