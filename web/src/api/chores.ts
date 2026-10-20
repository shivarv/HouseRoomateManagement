import type { Chore, HouseholdTasksToday, MyTasksToday, ScheduleDay, Task } from "../types/api";
import { api } from "./client";

export const choresApi = {
  list: (householdId: string) => api<Chore[]>(`/households/${householdId}/chores`),
  create: (householdId: string, name: string) =>
    api<Chore>(`/households/${householdId}/chores`, { method: "POST", body: { name } }),
  update: (choreId: string, changes: { name?: string; is_active?: boolean }) =>
    api<Chore>(`/chores/${choreId}`, { method: "PATCH", body: changes }),
  setRotation: (choreId: string, memberIds: string[]) =>
    api<Chore>(`/chores/${choreId}/rotation`, { method: "PUT", body: { member_ids: memberIds } }),
  remove: (choreId: string) => api<void>(`/chores/${choreId}`, { method: "DELETE" }),

  schedule: (householdId: string, days = 7) =>
    api<{ days: ScheduleDay[] }>(`/households/${householdId}/schedule?days=${days}`),
};

export const tasksApi = {
  mine: () => api<MyTasksToday>("/me/tasks/today"),
  householdToday: (householdId: string) =>
    api<HouseholdTasksToday>(`/households/${householdId}/tasks/today`),
  complete: (taskId: string) => api<Task>(`/tasks/${taskId}/complete`, { method: "POST" }),
  reopen: (taskId: string) => api<Task>(`/tasks/${taskId}/reopen`, { method: "POST" }),
};
