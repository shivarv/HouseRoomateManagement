import { Navigate, Route, Routes } from "react-router";
import { AppShell } from "./components/AppShell";
import { AuthPage } from "./pages/AuthPage";
import { AddHouseholdPage, HouseholdsPage } from "./pages/HouseholdsPage";
import { MyDayPage } from "./pages/MyDayPage";
import { HelpRequestsPage, NotificationsPage } from "./pages/NotificationsPage";
import { ActivityTab } from "./pages/household/ActivityTab";
import { ChoresTab } from "./pages/household/ChoresTab";
import { GroceriesTab } from "./pages/household/GroceriesTab";
import { GrocerySettingsPage } from "./pages/household/GrocerySettings";
import { HouseholdLayout } from "./pages/household/HouseholdLayout";
import { HouseLayout } from "./pages/household/HouseLayout";
import { PeopleTab } from "./pages/household/PeopleTab";
import { RemindersTab } from "./pages/household/RemindersTab";
import { BillSettingsPage } from "./pages/household/BillSettings";
import { HistoryTab, ReportTab } from "./pages/household/ReportTab";
import { ScheduleTab } from "./pages/household/ScheduleTab";
import { HouseDetailsSettings, SettingsLayout } from "./pages/household/SettingsPages";
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
        <Route path="households/new" element={<AddHouseholdPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="help" element={<HelpRequestsPage />} />
        <Route path="households/:householdId" element={<HouseholdLayout />}>
          {/* "Today" was merged into My day. */}
          <Route index element={<Navigate to="/" replace />} />
          <Route path="activity" element={<ActivityTab />} />
          {/* 🏡 House: Schedule, Report and People together. */}
          <Route path="house" element={<HouseLayout />}>
            <Route index element={<Navigate to="schedule" replace />} />
            <Route path="schedule" element={<ScheduleTab />} />
            <Route path="report" element={<ReportTab />} />
            <Route path="people" element={<PeopleTab />} />
          </Route>
          {/* Old addresses, kept for bookmarks. */}
          <Route path="report" element={<Navigate to="../house/report" replace />} />
          <Route path="schedule" element={<Navigate to="../house/schedule" replace />} />
          <Route path="people" element={<Navigate to="../house/people" replace />} />
          <Route path="chores" element={<ChoresTab />} />
          <Route path="groceries" element={<GroceriesTab />} />
          <Route path="reminders" element={<RemindersTab />} />
          {/* Admin-only configuration, kept apart from the everyday tabs. */}
          <Route path="settings" element={<SettingsLayout />}>
            <Route index element={<HouseDetailsSettings />} />
            <Route path="people" element={<PeopleTab manage />} />
            <Route path="chores" element={<ChoresTab manage />} />
            <Route path="groceries" element={<GrocerySettingsPage />} />
            <Route path="reminders" element={<BillSettingsPage />} />
            <Route path="history" element={<HistoryTab />} />
          </Route>
          <Route path="history" element={<Navigate to="../settings/history" replace />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
