import type {
  ActivityEvent,
  AssignmentMode,
  Chore,
  ChoreLog,
  Frequency,
  HouseholdTasksToday,
  MyTasksToday,
  Report,
  ScheduleDay,
  Swap,
  Task,
} from "../types/api";
import { api } from "./client";

export interface ChoreSettings {
  name?: string;
  is_active?: boolean;
  frequency?: Frequency;
  assignment_mode?: AssignmentMode;
  target_per_week?: number | null;
}

export const choresApi = {
  list: (householdId: string) => api<Chore[]>(`/households/${householdId}/chores`),
  create: (householdId: string, settings: ChoreSettings & { name: string }) =>
    api<Chore>(`/households/${householdId}/chores`, { method: "POST", body: settings }),
  update: (choreId: string, changes: ChoreSettings) =>
    api<Chore>(`/chores/${choreId}`, { method: "PATCH", body: changes }),
  setRotation: (choreId: string, memberIds: string[]) =>
    api<Chore>(`/chores/${choreId}/rotation`, { method: "PUT", body: { member_ids: memberIds } }),
  remove: (choreId: string) => api<void>(`/chores/${choreId}`, { method: "DELETE" }),

  schedule: (householdId: string, days = 7) =>
    api<{ days: ScheduleDay[] }>(`/households/${householdId}/schedule?days=${days}`),

  log: (choreId: string, memberId?: string) =>
    api<ChoreLog>(`/chores/${choreId}/logs`, { method: "POST", body: { member_id: memberId ?? null } }),
  removeLog: (logId: string) => api<void>(`/chore-logs/${logId}`, { method: "DELETE" }),
};

export const tasksApi = {
  mine: () => api<MyTasksToday>("/me/tasks/today"),
  householdToday: (householdId: string) => api<HouseholdTasksToday>(`/households/${householdId}/tasks/today`),
  complete: (taskId: string, completedBy?: string) =>
    api<Task>(`/tasks/${taskId}/complete`, { method: "POST", body: { completed_by_member_id: completedBy ?? null } }),
  reopen: (taskId: string) => api<Task>(`/tasks/${taskId}/reopen`, { method: "POST" }),
};

export const swapsApi = {
  ask: (choreId: string, dueDate: string, note?: string) =>
    api<Swap>(`/chores/${choreId}/swaps`, { method: "POST", body: { due_date: dueDate, note: note || null } }),
  householdOpen: (householdId: string) => api<Swap[]>(`/households/${householdId}/swaps`),
  mine: () => api<Swap[]>("/me/swaps"),
  accept: (swapId: string) => api<Swap>(`/swaps/${swapId}/accept`, { method: "POST" }),
  cancel: (swapId: string) => api<Swap>(`/swaps/${swapId}/cancel`, { method: "POST" }),
};

export const reportsApi = {
  activityMonth: (householdId: string, month: string) =>
    api<ActivityEvent[]>(`/households/${householdId}/activity?month=${month}`),
  report: (householdId: string, month?: string) =>
    api<Report>(`/households/${householdId}/report${month ? `?month=${month}` : ""}`),
  months: (householdId: string) => api<{ months: string[] }>(`/households/${householdId}/report/months`),
};
