import type { HelpRequest } from "../types/api";
import { api } from "./client";

export const helpApi = {
  list: () => api<HelpRequest[]>("/me/help-requests"),
  create: (householdId: string, title: string, details?: string) =>
    api<HelpRequest>(`/households/${householdId}/help-requests`, {
      method: "POST",
      body: { title, details: details || null },
    }),
  update: (id: string, changes: { title?: string; details?: string }) =>
    api<HelpRequest>(`/help-requests/${id}`, { method: "PATCH", body: changes }),
  done: (id: string) => api<HelpRequest>(`/help-requests/${id}/done`, { method: "POST" }),
  reopen: (id: string) => api<HelpRequest>(`/help-requests/${id}/reopen`, { method: "POST" }),
  withdraw: (id: string) => api<void>(`/help-requests/${id}`, { method: "DELETE" }),
};
