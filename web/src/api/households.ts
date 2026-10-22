import type { Household, HouseholdDetail, InvitePreview, Member } from "../types/api";
import { api } from "./client";

export const householdsApi = {
  list: () => api<Household[]>("/households"),
  get: (id: string) => api<HouseholdDetail>(`/households/${id}`),
  create: (name: string, timezone: string) =>
    api<Household>("/households", { method: "POST", body: { name, timezone } }),
  update: (id: string, changes: { name?: string; timezone?: string }) =>
    api<Household>(`/households/${id}`, { method: "PATCH", body: changes }),

  addMember: (householdId: string, displayName: string) =>
    api<Member>(`/households/${householdId}/members`, {
      method: "POST",
      body: { display_name: displayName },
    }),
  updateMember: (memberId: string, changes: { display_name?: string; role?: Member["role"] }) =>
    api<Member>(`/members/${memberId}`, { method: "PATCH", body: changes }),
  removeMember: (memberId: string) => api<void>(`/members/${memberId}`, { method: "DELETE" }),

  previewInvite: (code: string) => api<InvitePreview>(`/invites/${encodeURIComponent(code)}`),
  acceptInvite: (code: string, memberId: string | null) =>
    api<Household>(`/invites/${encodeURIComponent(code)}/accept`, {
      method: "POST",
      body: { member_id: memberId },
    }),
};
